"""Download da API REST do SAPL (Interlegis) de uma câmara municipal.

A API devolve no máximo 100 registros por página e leva alguns segundos por página, então as
páginas são pedidas em paralelo, com poucas conexões. Cada endpoint vira um JSON (lista de
registros ordenada por id) e entra no manifesto com o SHA-256 do conteúdo, como na Câmara.
"""

import hashlib
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import httpx

from polaritics.coleta.camara import RegistroArquivo
from polaritics.municipal.config import Municipio

log = logging.getLogger(__name__)

# nome do arquivo → endpoint da API
ENDPOINTS = {
    "legislatura": "parlamentares/legislatura",
    "parlamentar": "parlamentares/parlamentar",
    "mandato": "parlamentares/mandato",
    "filiacao": "parlamentares/filiacao",
    "partido": "parlamentares/partido",
    "tipoautor": "base/tipoautor",
    "autor": "base/autor",
    "tipomateria": "materia/tipomaterialegislativa",
    "materia": "materia/materialegislativa",
    "tiposessao": "sessao/tiposessaoplenaria",
    "sessao": "sessao/sessaoplenaria",
    "presenca": "sessao/sessaoplenariapresenca",
    "registrovotacao": "sessao/registrovotacao",
    "votoparlamentar": "sessao/votoparlamentar",
}
# Numa câmara que migrou para o Siscam, o SAPL só vale até a sua última votação, e estes
# arquivos não mudam mais: já baixados, não são baixados de novo (salvo com `forcar`). O
# cadastro, pequeno, é sempre atualizado.
CONGELADOS_COM_SISCAM = ("materia", "sessao", "presenca", "registrovotacao", "votoparlamentar")
# Campos de auditoria interna do SAPL (IP e usuário de quem registrou): não interessam e não
# devem ser guardados.
CAMPOS_DESCARTADOS = {"ip", "user", "biografia"}
POR_PAGINA = 100
CONEXOES = 4
TENTATIVAS = 4
ESPERA_BASE_S = 2.0


def endpoints_a_baixar(municipio: Municipio, forcar: bool = False) -> dict[str, str]:
    """Endpoints do SAPL a baixar: todos, menos os congelados já baixados (câmara com Siscam)."""
    return {
        nome: endpoint
        for nome, endpoint in ENDPOINTS.items()
        if forcar
        or not municipio.siscam
        or nome not in CONGELADOS_COM_SISCAM
        or not (municipio.dir_brutos / f"{nome}.json").exists()
    }


class ErroColetaSAPL(RuntimeError):
    pass


class ColetorSAPL:
    def __init__(self, municipio: Municipio, destino: Path | None = None, cliente=None):
        self.municipio = municipio
        self.destino = destino or municipio.dir_brutos
        self.cliente = cliente or httpx.Client(timeout=120, follow_redirects=True)
        self.caminho_manifesto = self.destino / "manifesto.json"

    def coletar(self, endpoints: dict[str, str] = ENDPOINTS) -> dict[str, int]:
        self.destino.mkdir(parents=True, exist_ok=True)
        manifesto = self._ler_manifesto()
        contagem = {}
        for nome, endpoint in endpoints.items():
            registros = self.baixar_endpoint(endpoint)
            conteudo = json.dumps(registros, ensure_ascii=False, sort_keys=True).encode()
            sha256 = hashlib.sha256(conteudo).hexdigest()
            (self.destino / f"{nome}.json").write_bytes(conteudo)
            agora = datetime.now(UTC).isoformat(timespec="seconds")
            anterior = manifesto.get(f"{nome}.json")
            mudou = anterior is None or anterior.sha256 != sha256
            manifesto[f"{nome}.json"] = RegistroArquivo(
                url=self._url(endpoint),
                sha256=sha256,
                bytes=len(conteudo),
                baixado_em=agora,
                alterado_em=agora if mudou else anterior.alterado_em,
            )
            contagem[nome] = len(registros)
            log.info(
                "%s: %d registros (%s)", nome, len(registros), "alterado" if mudou else "igual"
            )
        self.caminho_manifesto.write_text(
            json.dumps({k: asdict(v) for k, v in sorted(manifesto.items())}, indent=2) + "\n",
            encoding="utf-8",
        )
        return contagem

    def baixar_endpoint(self, endpoint: str) -> list[dict]:
        primeira = self._get(endpoint, 1)
        paginacao = primeira["pagination"]
        with ThreadPoolExecutor(CONEXOES) as ex:
            demais = list(
                ex.map(lambda p: self._get(endpoint, p), range(2, paginacao["total_pages"] + 1))
            )
        registros = [r for pagina in (primeira, *demais) for r in pagina["results"]]
        if len(registros) != paginacao["total_entries"]:
            raise ErroColetaSAPL(
                f"{endpoint}: {len(registros)} registros baixados, a API informa "
                f"{paginacao['total_entries']} (base mudou durante a coleta?)"
            )
        ids = [r["id"] for r in registros]
        if len(set(ids)) != len(ids):
            raise ErroColetaSAPL(f"{endpoint}: ids repetidos entre páginas")
        return sorted(
            ({k: v for k, v in r.items() if k not in CAMPOS_DESCARTADOS} for r in registros),
            key=lambda r: r["id"],
        )

    def _url(self, endpoint: str) -> str:
        return f"{self.municipio.sapl}/api/{endpoint}/"

    def _get(self, endpoint: str, pagina: int) -> dict:
        # sem ordem explícita a API pagina em ordem instável e repete ou pula registros
        params = {"page": pagina, "page_size": POR_PAGINA, "o": "id"}
        for tentativa in range(1, TENTATIVAS + 1):
            try:
                resposta = self.cliente.get(self._url(endpoint), params=params)
                resposta.raise_for_status()
                return resposta.json()
            except (httpx.TransportError, httpx.HTTPStatusError) as erro:
                transitorio = not isinstance(erro, httpx.HTTPStatusError) or (
                    erro.response.status_code >= 500
                )
                if not transitorio or tentativa == TENTATIVAS:
                    raise ErroColetaSAPL(f"falha em {endpoint} página {pagina}: {erro}") from erro
                time.sleep(ESPERA_BASE_S * 2 ** (tentativa - 1))
        raise AssertionError("inalcançável")

    def _ler_manifesto(self) -> dict[str, RegistroArquivo]:
        if not self.caminho_manifesto.exists():
            return {}
        dados = json.loads(self.caminho_manifesto.read_text(encoding="utf-8"))
        return {nome: RegistroArquivo(**reg) for nome, reg in dados.items()}
