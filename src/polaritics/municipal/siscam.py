"""Coleta das votações no Siscam (Sino Informática), sistema que substituiu o SAPL em Franca.

A base usa o Siscam só depois da última votação do SAPL: o histórico migrado para o Siscam tem
votações ligadas a sessões erradas (metodologia municipal, M1). A coleta, porém, baixa tudo,
para que a conferência entre as fontes possa ser refeita.

O Siscam não tem API, e a exportação em CSV devolve erro no servidor. A listagem de votações
em HTML, porém, já traz cada votação com os votos agrupados ("A Favor (7): …", "Contra (6): …",
"Não votaram (1): …"). A coleta percorre a listagem das votações nominais, 100 por página,
e grava os registros interpretados em JSON. Os vereadores aparecem como "Nome Civil (Nome
Parlamentar)"; a ligação com o cadastro do SAPL é feita pelo nome parlamentar, na base.
"""

import hashlib
import html
import json
import logging
import re
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import httpx

from polaritics.coleta.camara import RegistroArquivo

log = logging.getLogger(__name__)

TIPO_VOTACAO_NOMINAL = 1
POR_PAGINA = 100
TENTATIVAS = 4
ESPERA_BASE_S = 2.0
PAUSA_ENTRE_PAGINAS_S = 0.5


class ErroColetaSiscam(RuntimeError):
    pass


def _texto(fragmento: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragmento)).split())


def _campo(item: str, rotulo: str) -> list[str]:
    """Valores dos campos "<strong>Rótulo:</strong> valor" do item, na ordem da página."""
    padrao = rf"<strong>\s*{rotulo}:\s*</strong>(.*?)</p>"
    return [_texto(v) for v in re.findall(padrao, item, flags=re.S)]


def _data(texto: str) -> str | None:
    if m := re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", texto):
        return f"{m[3]}-{m[2]}-{m[1]}"
    return None


# "Nome Civil (Nome Parlamentar)", separados por vírgula
VOTANTE = re.compile(r"\s*([^,()]+?)\s*\(([^()]+)\)\s*(?:,|$)")


def votantes(texto: str) -> list[dict]:
    achados = [{"nome_civil": a, "nome": b} for a, b in VOTANTE.findall(texto)]
    if not achados and texto.strip():
        raise ErroColetaSiscam(f"lista de votantes em formato inesperado: {texto[:120]!r}")
    return achados


def _grupos(item: str, rotulo_item: str) -> dict[str, list[dict]]:
    """Grupos "<strong>Grupo (n):</strong> Nome (Apelido), …", conferindo cada contagem."""
    grupos = {}
    for grupo, n, nomes in re.findall(
        r"<strong>\s*([^<:]+?)\s*\((\d+)\):\s*</strong>(.*?)</p>", item, flags=re.S
    ):
        lista = votantes(_texto(nomes))
        if len(lista) != int(n):
            raise ErroColetaSiscam(
                f"{rotulo_item}: '{_texto(grupo)}' informa {n} nomes, a lista tem {len(lista)}"
            )
        grupos[_texto(grupo)] = lista
    return grupos


def interpretar_listagem(pagina: str, recurso: str = "Votacoes") -> tuple[list[dict], int]:
    """Registros de uma página da listagem (`Votacoes` ou `Frequencias`) e o total informado."""
    total = re.search(r"([\d.]+)\s+registros?\s+encontrados?", pagina)
    if not total:
        raise ErroColetaSiscam("a página não informa o total de registros")
    registros = []
    for item in pagina.split('class="data-list-item"')[1:]:
        titulo = re.search(
            rf'<h4>\s*<a href="/Siscam/{recurso}/Details\?id=(\d+)">(.*?)</a>', item, re.S
        )
        if not titulo:
            raise ErroColetaSiscam(f"item sem link para /Siscam/{recurso}")
        sessao = re.search(r'Reunioes/Details\?id=(\d+)">(.*?)</a>', item, re.S)
        datas = [_data(d) for d in _campo(item, "Data")]
        registro = {
            "id": int(titulo[1]),
            "titulo": _texto(titulo[2]),
            "id_sessao": int(sessao[1]) if sessao else None,
            "sessao": _texto(sessao[2]) if sessao else None,
            # nas votações, o primeiro "Data" é o do documento e o último, o da votação
            "data": datas[-1] if datas else None,
            "grupos": _grupos(item, f"{recurso} {titulo[1]}"),
        }
        if recurso == "Votacoes":
            registro |= {
                "data_documento": datas[0] if len(datas) > 1 else None,
                "ementa": next(iter(_campo(item, "Ementa")), None),
                "autoria": next(iter(_campo(item, "Autoria") + _campo(item, "Autor")), None),
                "tipo": next(iter(_campo(item, "Tipo")), None),
                "resultado": next(iter(_campo(item, "Resultado")), None),
            }
        registros.append(registro)
    return registros, int(total[1].replace(".", ""))


class ColetorSiscam:
    def __init__(self, url_base: str, destino: Path, cliente: httpx.Client | None = None):
        self.url_base = url_base.rstrip("/")
        self.destino = destino
        self.cliente = cliente or httpx.Client(timeout=120, follow_redirects=True)
        self.caminho_manifesto = destino / "manifesto.json"

    def coletar(self) -> dict[str, int]:
        """Votações nominais e frequências das sessões, cada uma num JSON."""
        self.destino.mkdir(parents=True, exist_ok=True)
        return {
            "votacoes": self._listar(
                "Votacoes", {"TipoVotacaoId": TIPO_VOTACAO_NOMINAL}, "siscam_votacoes.json"
            ),
            "frequencias": self._listar("Frequencias", {}, "siscam_frequencias.json"),
        }

    def _listar(self, recurso: str, filtros: dict, arquivo: str) -> int:
        registros, total = self._pagina(recurso, filtros, 1)
        paginas = -(-total // POR_PAGINA)
        for p in range(2, paginas + 1):
            time.sleep(PAUSA_ENTRE_PAGINAS_S)
            registros += self._pagina(recurso, filtros, p)[0]
            if p % 10 == 0:
                log.info("siscam %s: página %d/%d", recurso, p, paginas)
        ids = [r["id"] for r in registros]
        if len(set(ids)) != len(ids) or len(ids) != total:
            raise ErroColetaSiscam(
                f"{recurso}: {len(set(ids))} registros distintos em {len(ids)}; o Siscam informa "
                f"{total} (a listagem mudou durante a coleta?)"
            )
        registros.sort(key=lambda r: r["id"])
        self._gravar(arquivo, self._url(recurso), registros)
        return total

    def _url(self, recurso: str) -> str:
        return f"{self.url_base}/Siscam/{recurso}"

    def _pagina(self, recurso: str, filtros: dict, pagina: int) -> tuple[list[dict], int]:
        params = {**filtros, "ItemsPerPage": POR_PAGINA, "CurrentPage": pagina}
        for tentativa in range(1, TENTATIVAS + 1):
            try:
                resposta = self.cliente.get(self._url(recurso), params=params)
                resposta.raise_for_status()
                return interpretar_listagem(resposta.text, recurso)
            except (httpx.TransportError, httpx.HTTPStatusError) as erro:
                if tentativa == TENTATIVAS:
                    raise ErroColetaSiscam(f"falha em {recurso}, página {pagina}: {erro}") from erro
                time.sleep(ESPERA_BASE_S * 2 ** (tentativa - 1))
        raise AssertionError("inalcançável")

    def _gravar(self, nome: str, url: str, registros: list[dict]) -> None:
        conteudo = json.dumps(registros, ensure_ascii=False, sort_keys=True).encode()
        sha256 = hashlib.sha256(conteudo).hexdigest()
        (self.destino / nome).write_bytes(conteudo)
        manifesto = (
            json.loads(self.caminho_manifesto.read_text(encoding="utf-8"))
            if self.caminho_manifesto.exists()
            else {}
        )
        anterior = manifesto.get(nome)
        agora = datetime.now(UTC).isoformat(timespec="seconds")
        mudou = anterior is None or anterior["sha256"] != sha256
        manifesto[nome] = asdict(
            RegistroArquivo(
                url=url,
                sha256=sha256,
                bytes=len(conteudo),
                baixado_em=agora,
                alterado_em=agora if mudou else anterior["alterado_em"],
            )
        )
        self.caminho_manifesto.write_text(
            json.dumps(dict(sorted(manifesto.items())), indent=2) + "\n", encoding="utf-8"
        )
