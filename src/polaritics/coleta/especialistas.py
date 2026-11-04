"""Classificação ideológica dos partidos por especialistas (âncora da escala 0–10).

Fonte: Bolognesi, Ribeiro, Codato & Silva, "Database on the ideological classification of all
Brazilian political parties (2018-2022)", Harvard Dataverse, doi:10.7910/DVN/MFIXKW, CC0 1.0.
Uma linha por especialista; colunas `ideol_22_<partido>` com notas de 0 (extrema esquerda) a
10 (extrema direita) na onda de 2022.

O hash do arquivo é fixado: se os autores publicarem nova versão, a coleta falha de propósito
para que a mudança de âncora seja uma decisão consciente (e versionada na metodologia).
"""

import csv
import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, stdev

import httpx

from polaritics.base.partidos import SUCESSORES
from polaritics.config import DIR_BRUTOS

log = logging.getLogger(__name__)

DOI = "doi:10.7910/DVN/MFIXKW"
URL = "https://dataverse.harvard.edu/api/access/datafile/10898288"
SHA256 = "74fe0ac6948c4da4bc0c8e824d547159d9c6adcec10c8cafcefec574c90d6754"
ARQUIVO = DIR_BRUTOS / "especialistas" / "df_experts.csv"

# Sufixo da coluna na onda de 2022 → sigla usada pela Câmara.
COLUNAS_2022 = {
    "mdb": "MDB",
    "uniao": "UNIÃO",
    "ptb": "PTB",
    "pdt": "PDT",
    "pt": "PT",
    "p_cdo_b": "PCdoB",
    "psb": "PSB",
    "psdb": "PSDB",
    "agir": "AGIR",
    "psc": "PSC",
    "pmn": "MOBILIZA",  # o PMN passou a se chamar Mobiliza
    "cdd": "CIDADANIA",
    "pv": "PV",
    "avante": "AVANTE",
    "progre": "PP",
    "pstu": "PSTU",
    "pcb": "PCB",
    "prtb": "PRTB",
    "dc": "DC",
    "pco": "PCO",
    "podemos": "PODE",
    "rep": "REPUBLICANOS",
    "psol": "PSOL",
    "pl": "PL",
    "psd": "PSD",
    "patri": "PATRIOTA",
    "pros": "PROS",
    "sdd": "SOLIDARIEDADE",
    "novo": "NOVO",
    "rede": "REDE",
    "pmb": "PMB",
    "up": "UP",
}


class ErroEspecialistas(RuntimeError):
    pass


@dataclass(frozen=True)
class NotaPartido:
    partido: str
    nota: float
    n_respostas: int | None
    desvio_padrao: float | None
    origem: str  # "direta" ou "fusão de X + Y"


def baixar(destino: Path = ARQUIVO, cliente: httpx.Client | None = None) -> Path:
    cliente = cliente or httpx.Client(timeout=120, follow_redirects=True)
    resposta = cliente.get(URL)
    resposta.raise_for_status()
    if (obtido := hashlib.sha256(resposta.content).hexdigest()) != SHA256:
        raise ErroEspecialistas(
            f"o arquivo de {DOI} mudou (sha256 {obtido}); revise a âncora antes de atualizar"
        )
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(resposta.content)
    log.info("notas dos especialistas salvas em %s", destino)
    return destino


def _respostas(arquivo: Path) -> dict[str, list[float]]:
    respostas: dict[str, list[float]] = {sigla: [] for sigla in COLUNAS_2022.values()}
    with arquivo.open(encoding="utf-8-sig", newline="") as f:
        for linha in csv.DictReader(f, delimiter=";"):
            for sufixo, sigla in COLUNAS_2022.items():
                if valor := (linha.get(f"ideol_22_{sufixo}") or "").strip():
                    respostas[sigla].append(float(valor.replace(",", ".")))
    return respostas


def notas_2022(arquivo: Path = ARQUIVO) -> list[NotaPartido]:
    """Média das notas por partido. Fusões ganham a média dos partidos de origem;
    incorporações mantêm a nota do partido incorporador."""
    respostas = _respostas(arquivo)
    notas = {
        sigla: NotaPartido(sigla, mean(vs), len(vs), stdev(vs), "direta")
        for sigla, vs in respostas.items()
        if len(vs) >= 2
    }
    fusoes: dict[str, list[str]] = {}
    for extinto, sucessao in SUCESSORES.items():
        if sucessao.tipo == "fusao" and extinto in notas:
            fusoes.setdefault(sucessao.sucessor, []).append(extinto)
    for novo, origens in fusoes.items():
        notas[novo] = NotaPartido(
            novo,
            mean(notas[o].nota for o in origens),
            None,
            None,
            "fusão de " + " + ".join(sorted(origens)),
        )
    return sorted(notas.values(), key=lambda n: n.partido)
