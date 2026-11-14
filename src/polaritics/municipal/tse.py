"""Prestação de contas de campanha dos vereadores (TSE, dados abertos), metodologia municipal M12.

Os pacotes do TSE têm mais de 1 GB por eleição, com um CSV por UF dentro. Como o ZIP guarda o
índice no fim do arquivo, a coleta lê por HTTP Range só o índice e os CSVs de uma UF, e grava
apenas as linhas do município. Os dados de uma eleição não mudam depois de fechados: já
baixados, não são baixados de novo.

Só entram campos agregáveis (origem e valor das receitas e despesas). Nomes e CPF de doadores
pessoas físicas não são gravados.
"""

import csv
import io
import logging
import zipfile
from pathlib import Path

import httpx

from polaritics.municipal.siscam import gravar_com_manifesto

log = logging.getLogger(__name__)

CDN = "https://cdn.tse.jus.br/estatistica/sead/odsele"
CARGO_VEREADOR = "13"
ELEICOES = (2020, 2024)
BLOCO = 1 << 20  # leituras de 1 MiB

CAMPOS_CANDIDATO = (
    "SQ_CANDIDATO", "NM_CANDIDATO", "NM_URNA_CANDIDATO", "SG_PARTIDO", "DS_SIT_TOT_TURNO",
)  # fmt: skip
CAMPOS_RECEITA = ("SQ_CANDIDATO", "DS_ORIGEM_RECEITA", "DS_FONTE_RECEITA", "VR_RECEITA")
CAMPOS_DESPESA = ("SQ_CANDIDATO", "DS_ORIGEM_DESPESA", "VR_DESPESA_CONTRATADA")


class ArquivoRemoto(io.RawIOBase):
    """Arquivo somente leitura sobre HTTP Range, para o `zipfile` ler só o que precisa."""

    def __init__(self, url: str, cliente: httpx.Client):
        self.url, self.cliente, self.posicao = url, cliente, 0
        resposta = cliente.head(url)
        resposta.raise_for_status()
        if resposta.headers.get("accept-ranges") != "bytes":
            raise OSError(f"{url} não aceita leitura por faixas")
        self.tamanho = int(resposta.headers["content-length"])

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.posicao

    def seek(self, deslocamento: int, origem: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.posicao, io.SEEK_END: self.tamanho}[origem]
        self.posicao = base + deslocamento
        return self.posicao

    def readinto(self, destino) -> int:
        if self.posicao >= self.tamanho:
            return 0
        fim = min(self.posicao + len(destino), self.tamanho) - 1
        resposta = self.cliente.get(self.url, headers={"Range": f"bytes={self.posicao}-{fim}"})
        if resposta.status_code != 206:
            raise OSError(f"{self.url}: faixa recusada ({resposta.status_code})")
        dados = resposta.content
        destino[: len(dados)] = dados
        self.posicao += len(dados)
        return len(dados)


def _linhas(zip_remoto: zipfile.ZipFile, padrao: str, uf: str) -> csv.DictReader:
    nomes = [n for n in zip_remoto.namelist() if padrao in n and n.endswith(f"_{uf}.csv")]
    if len(nomes) != 1:
        raise ValueError(f"esperado um arquivo '{padrao}…_{uf}.csv', achei {nomes}")
    texto = io.TextIOWrapper(zip_remoto.open(nomes[0]), encoding="latin-1", newline="")
    return csv.DictReader(texto, delimiter=";")


def _abrir(url: str, cliente: httpx.Client) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BufferedReader(ArquivoRemoto(url, cliente), buffer_size=BLOCO))


def coletar_eleicao(
    ano: int, municipio_tse: str, uf: str, destino: Path, cliente: httpx.Client
) -> dict[str, int]:
    """Candidatos a vereador, receitas e despesas de campanha do município na eleição."""
    url_cand = f"{CDN}/consulta_cand/consulta_cand_{ano}.zip"
    with _abrir(url_cand, cliente) as z:
        candidatos = [
            {c: linha[c] for c in CAMPOS_CANDIDATO}
            for linha in _linhas(z, f"consulta_cand_{ano}", uf)
            if linha["NM_UE"] == municipio_tse and linha["CD_CARGO"] == CARGO_VEREADOR
        ]
    sequenciais = {c["SQ_CANDIDATO"] for c in candidatos}
    if not sequenciais:
        raise ValueError(f"nenhum candidato a vereador em {municipio_tse}/{uf} em {ano}")
    url_contas = f"{CDN}/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_{ano}.zip"
    with _abrir(url_contas, cliente) as z:
        receitas = [
            {c: linha[c] for c in CAMPOS_RECEITA}
            for linha in _linhas(z, f"receitas_candidatos_{ano}", uf)
            if linha["SQ_CANDIDATO"] in sequenciais
        ]
        despesas = [
            {c: linha[c] for c in CAMPOS_DESPESA}
            for linha in _linhas(z, f"despesas_contratadas_candidatos_{ano}", uf)
            if linha["SQ_CANDIDATO"] in sequenciais
        ]
    for nome, registros, url in (
        (f"tse_candidatos_{ano}.json", candidatos, url_cand),
        (f"tse_receitas_{ano}.json", receitas, url_contas),
        (f"tse_despesas_{ano}.json", despesas, url_contas),
    ):
        gravar_com_manifesto(destino, nome, url, registros)
    log.info("TSE %d: %d candidatos, %d receitas", ano, len(candidatos), len(receitas))
    return {"candidatos": len(candidatos), "receitas": len(receitas), "despesas": len(despesas)}


def coletar(municipio_tse: str, uf: str, destino: Path, forcar: bool = False) -> dict:
    cliente = httpx.Client(timeout=300, follow_redirects=True)
    contagem = {}
    for ano in ELEICOES:
        if not forcar and (destino / f"tse_despesas_{ano}.json").exists():
            continue
        contagem[ano] = coletar_eleicao(ano, municipio_tse, uf, destino, cliente)
    return contagem
