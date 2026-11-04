"""Download dos arquivos em lote dos Dados Abertos da Câmara dos Deputados.

O servidor regera todos os arquivos diariamente (inclusive de anos encerrados), então
Last-Modified/ETag não indicam mudança real. Cada arquivo é identificado pelo SHA-256 do
conteúdo e registrado no manifesto. Anos encerrados só são baixados de novo com `forcar=True`.
"""

import csv
import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import httpx

from polaritics.config import DIR_BRUTOS, LEGISLATURAS

log = logging.getLogger(__name__)

URL_BASE = "https://dadosabertos.camara.leg.br/arquivos"

# Arquivo → colunas que precisam existir (validação mínima do formato).
ARQUIVOS_ANUAIS = {
    "votacoes": {"id", "data", "siglaOrgao", "descricao"},
    "votacoesVotos": {"idVotacao", "voto", "deputado_id", "deputado_siglaPartido"},
    "votacoesOrientacoes": {"idVotacao", "siglaBancada", "orientacao"},
    "votacoesObjetos": {"idVotacao", "proposicao_id", "proposicao_siglaTipo"},
    "votacoesProposicoes": {"idVotacao", "proposicao_id"},
    "proposicoesTemas": {"uriProposicao", "tema"},
}
ARQUIVOS_UNICOS = {
    "deputados": {"uri", "nome", "idLegislaturaInicial"},
    "legislaturas": {"idLegislatura", "dataInicio", "dataFim"},
}

TENTATIVAS = 3
ESPERA_BASE_S = 2.0


class ErroColeta(RuntimeError):
    pass


@dataclass
class RegistroArquivo:
    url: str
    sha256: str
    bytes: int
    baixado_em: str
    alterado_em: str  # última vez em que o conteúdo (hash) mudou


def url_arquivo(nome: str, ano: int | None = None) -> str:
    arquivo = f"{nome}-{ano}" if ano else nome
    return f"{URL_BASE}/{nome}/csv/{arquivo}.csv"


def anos_a_atualizar(legislatura: int, hoje: date, forcar: bool) -> list[int]:
    """Anos da legislatura já iniciados; sem `forcar`, só o ano corrente e o anterior."""
    anos = [a for a in LEGISLATURAS[legislatura].periodo.anos if a <= hoje.year]
    return anos if forcar else [a for a in anos if a >= hoje.year - 1]


class ColetorCamara:
    def __init__(self, destino: Path = DIR_BRUTOS / "camara", cliente: httpx.Client | None = None):
        self.destino = destino
        self.cliente = cliente or httpx.Client(timeout=120, follow_redirects=True)
        self.caminho_manifesto = destino / "manifesto.json"
        self.manifesto: dict[str, RegistroArquivo] = self._ler_manifesto()

    def _ler_manifesto(self) -> dict[str, RegistroArquivo]:
        if not self.caminho_manifesto.exists():
            return {}
        dados = json.loads(self.caminho_manifesto.read_text(encoding="utf-8"))
        return {nome: RegistroArquivo(**reg) for nome, reg in dados.items()}

    def _salvar_manifesto(self) -> None:
        dados = {nome: asdict(reg) for nome, reg in sorted(self.manifesto.items())}
        self.caminho_manifesto.write_text(
            json.dumps(dados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    def coletar(self, legislatura: int, hoje: date | None = None, forcar: bool = False) -> None:
        hoje = hoje or date.today()
        self.destino.mkdir(parents=True, exist_ok=True)
        for nome, colunas in ARQUIVOS_UNICOS.items():
            self.baixar(nome, None, colunas)
        todos_anos = [a for a in LEGISLATURAS[legislatura].periodo.anos if a <= hoje.year]
        for ano in todos_anos:
            atualizar = ano in anos_a_atualizar(legislatura, hoje, forcar)
            for nome, colunas in ARQUIVOS_ANUAIS.items():
                if not atualizar and (self.destino / f"{nome}-{ano}.csv").exists():
                    continue
                # o arquivo do ano corrente pode ainda não existir (ex.: início de janeiro)
                self.baixar(nome, ano, colunas, opcional=ano == hoje.year)
        self._salvar_manifesto()

    def baixar(
        self, nome: str, ano: int | None, colunas: set[str], opcional: bool = False
    ) -> RegistroArquivo | None:
        url = url_arquivo(nome, ano)
        arquivo = self.destino / Path(url).name
        temporario = arquivo.with_suffix(".csv.parcial")
        try:
            sha256, tamanho = self._baixar_com_tentativas(url, temporario)
        except FileNotFoundError:
            if opcional:
                log.info("ainda não publicado: %s", url)
                return None
            raise ErroColeta(f"arquivo não encontrado: {url}") from None
        validar_colunas(temporario, colunas)
        agora = datetime.now(UTC).isoformat(timespec="seconds")
        anterior = self.manifesto.get(arquivo.name)
        mudou = anterior is None or anterior.sha256 != sha256
        temporario.replace(arquivo)
        registro = RegistroArquivo(
            url=url,
            sha256=sha256,
            bytes=tamanho,
            baixado_em=agora,
            alterado_em=agora if mudou else anterior.alterado_em,
        )
        self.manifesto[arquivo.name] = registro
        log.info("%s %s (%d bytes)", "alterado" if mudou else "sem mudança", arquivo.name, tamanho)
        return registro

    def _baixar_com_tentativas(self, url: str, destino: Path) -> tuple[str, int]:
        for tentativa in range(1, TENTATIVAS + 1):
            try:
                return self._baixar(url, destino)
            except (httpx.TransportError, httpx.HTTPStatusError) as erro:
                transitorio = not isinstance(erro, httpx.HTTPStatusError) or (
                    erro.response.status_code >= 500
                )
                if not transitorio or tentativa == TENTATIVAS:
                    raise ErroColeta(f"falha ao baixar {url}: {erro}") from erro
                espera = ESPERA_BASE_S * 2 ** (tentativa - 1)
                log.warning(
                    "tentativa %d falhou (%s); nova tentativa em %.0fs", tentativa, erro, espera
                )
                time.sleep(espera)
        raise AssertionError("inalcançável")

    def _baixar(self, url: str, destino: Path) -> tuple[str, int]:
        hash_ = hashlib.sha256()
        tamanho = 0
        with self.cliente.stream("GET", url) as resposta:
            if resposta.status_code == 404:
                raise FileNotFoundError(url)
            resposta.raise_for_status()
            with destino.open("wb") as saida:
                for bloco in resposta.iter_bytes():
                    hash_.update(bloco)
                    tamanho += len(bloco)
                    saida.write(bloco)
        return hash_.hexdigest(), tamanho


MIN_VOTACOES_NOMINAIS_ANO_COMPLETO = 150  # observado em 2023–2025: 272 a 425


def contar_votacoes_nominais_plenario(arquivo: Path) -> int:
    # Votações nominais trazem o placar ("Total: 458") na descrição; simbólicas, não.
    with arquivo.open(encoding="utf-8-sig", newline="") as f:
        return sum(
            1
            for linha in csv.DictReader(f, delimiter=";")
            if linha["siglaOrgao"] == "PLEN" and "total:" in linha["descricao"].lower()
        )


def checar_sanidade(destino: Path, legislatura: int, hoje: date) -> dict[int, int]:
    """Falha se algum ano completo da legislatura tiver poucas votações nominais."""
    contagem = {}
    for ano in LEGISLATURAS[legislatura].periodo.anos:
        arquivo = destino / f"votacoes-{ano}.csv"
        if ano > hoje.year or not arquivo.exists():
            continue
        contagem[ano] = contar_votacoes_nominais_plenario(arquivo)
        if ano < hoje.year and contagem[ano] < MIN_VOTACOES_NOMINAIS_ANO_COMPLETO:
            raise ErroColeta(
                f"{arquivo.name}: só {contagem[ano]} votações nominais de plenário "
                f"(mínimo {MIN_VOTACOES_NOMINAIS_ANO_COMPLETO})"
            )
    return contagem


def validar_colunas(arquivo: Path, esperadas: set[str]) -> None:
    with arquivo.open(encoding="utf-8-sig", newline="") as f:
        cabecalho = set(next(csv.reader(f, delimiter=";"), []))
    if faltando := esperadas - cabecalho:
        arquivo.unlink()
        raise ErroColeta(f"{arquivo.name}: colunas ausentes {sorted(faltando)}")
