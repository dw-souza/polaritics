"""Pesquisa Legislativa Brasileira (Brazilian Legislative Surveys), usada só na validação.

Fonte: Power, T. J.; Zucco, C. Brazilian Legislative Surveys (Waves 1-9, 1990-2021), Harvard
Dataverse, doi:10.7910/DVN/WM9IZ8, CC0 1.0 (os autores pedem citação).

O download exige preencher o guestbook do Dataverse, então não é automático: o arquivo
BLS9_full.tab é baixado manualmente para data/raw/bls/. Para a atualização automática, o
repositório guarda só o resumo por partido (RESUMO), gerado deste arquivo por
`exportar_resumo`; os dados são CC0 e o resumo traz a citação pedida pelos autores.

As colunas `lr<partido>` trazem a posição de cada partido numa escala de 1 (esquerda) a 10
(direita), segundo os parlamentares entrevistados; -999 é ausência de resposta.
"""

import csv
import hashlib
from pathlib import Path
from statistics import mean

from polaritics.config import DIR_BRUTOS, RAIZ

DOI = "doi:10.7910/DVN/WM9IZ8"
CITACAO = (
    "Power, Timothy J.; Zucco, Cesar, 2023, Brazilian Legislative Surveys "
    "(Waves 1-9, 1990-2021), https://doi.org/10.7910/DVN/WM9IZ8, Harvard Dataverse, V1"
)
ARQUIVO = DIR_BRUTOS / "bls" / "BLS9_full.tab"
RESUMO = RAIZ / "dados" / "referencia" / "bls-2021-partidos.csv"
SHA256 = "85efc0cce79653e384e00160796076a498178202f0c67015617db341bd1b4efe"
ONDA = "2021"
MIN_RESPOSTAS = 10

# Coluna → sigla da Câmara. Partidos que deixaram de existir entram em FUSOES.
COLUNAS = {
    "lrpt": "PT",
    "lrpcdob": "PCdoB",
    "lrpsol": "PSOL",
    "lrpsb": "PSB",
    "lrpdt": "PDT",
    "lrrede": "REDE",
    "lrpv": "PV",
    "lrmdb": "MDB",
    "lrpsd": "PSD",
    "lrpsdb": "PSDB",
    "lrcid": "CIDADANIA",
    "lrsd": "SOLIDARIEDADE",
    "lrpode": "PODE",
    "lrpp_ppb": "PP",
    "lrrep": "REPUBLICANOS",
    "lrpl": "PL",
    "lrnovo": "NOVO",
    "lrdem": "DEM",
    "lrpsl": "PSL",
    "lrptb": "PTB",
}
# Fusão posterior à onda: o novo partido recebe a média das origens, desde que todas tenham
# nota (mesma regra das notas dos especialistas). O PRD (PTB + Patriota) fica sem nota porque
# o Patriota não está na pesquisa.
FUSOES = {"UNIÃO": ("DEM", "PSL"), "PRD": ("PTB", "PATRIOTA")}


class ErroBLS(RuntimeError):
    pass


def disponivel(arquivo: Path = ARQUIVO, resumo: Path = RESUMO) -> bool:
    return arquivo.exists() or resumo.exists()


def notas(
    arquivo: Path = ARQUIVO, verificar_hash: bool = True, resumo: Path = RESUMO
) -> dict[str, float]:
    """Média da posição de cada partido na onda de 2021 (partidos com ≥ MIN_RESPOSTAS).
    Usa o arquivo bruto se existir; senão, o resumo versionado no repositório."""
    if not arquivo.exists():
        with resumo.open(encoding="utf-8", newline="") as f:
            linhas = (linha for linha in f if not linha.startswith("#"))
            return {linha["partido"]: float(linha["nota"]) for linha in csv.DictReader(linhas)}
    if verificar_hash and hashlib.sha256(arquivo.read_bytes()).hexdigest() != SHA256:
        raise ErroBLS(f"{arquivo.name} difere do arquivo validado de {DOI}")
    respostas: dict[str, list[float]] = {sigla: [] for sigla in COLUNAS.values()}
    with arquivo.open(encoding="utf-8", newline="") as f:
        for linha in csv.DictReader(f, delimiter="\t"):
            if linha["wave"].strip('"') != ONDA:
                continue
            for coluna, sigla in COLUNAS.items():
                try:
                    valor = float(linha[coluna])
                except (KeyError, ValueError):
                    continue
                if 1 <= valor <= 10:
                    respostas[sigla].append(valor)
    resultado = {s: mean(vs) for s, vs in respostas.items() if len(vs) >= MIN_RESPOSTAS}
    for novo, origens in FUSOES.items():
        if all(o in resultado for o in origens):
            resultado[novo] = mean(resultado[o] for o in origens)
    return resultado


def exportar_resumo(
    destino: Path = RESUMO, arquivo: Path = ARQUIVO, verificar_hash: bool = True
) -> Path:
    """Grava as médias por partido (com a citação) para uso sem o arquivo bruto."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8", newline="") as f:
        f.write(f"# {CITACAO}. CC0 1.0. Onda {ONDA}; escala 1 (esquerda) a 10 (direita); ")
        f.write(f"média das respostas dos parlamentares, mínimo de {MIN_RESPOSTAS}.\n")
        w = csv.writer(f)
        w.writerow(["partido", "nota"])
        for partido, nota in sorted(notas(arquivo, verificar_hash).items()):
            w.writerow([partido, f"{nota:.4f}"])
    return destino
