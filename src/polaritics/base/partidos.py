"""Siglas partidárias: harmonização e sucessões (fusões e incorporações)."""

from datetime import date
from typing import Literal, NamedTuple

SEM_PARTIDO = "S.PART."


class Sucessao(NamedTuple):
    sucessor: str
    data_decisao: date  # decisão do TSE que aprovou a fusão/incorporação
    # incorporação: o sucessor já existia e mantém a identidade;
    # fusão: o sucessor é um partido novo.
    tipo: Literal["incorporacao", "fusao"]


# Partido extinto → sucessão.
SUCESSORES = {
    "PROS": Sucessao("SOLIDARIEDADE", date(2023, 2, 14), "incorporacao"),
    "PSC": Sucessao("PODE", date(2023, 6, 15), "incorporacao"),
    "PATRIOTA": Sucessao("PRD", date(2023, 11, 9), "fusao"),
    "PTB": Sucessao("PRD", date(2023, 11, 9), "fusao"),
}

# Grafias usadas por outras fontes → sigla da Câmara.
SINONIMOS = {
    "PC do B": "PCdoB",
    "PC DO B": "PCdoB",
    "Novo": "NOVO",
    "Podemos": "PODE",
    "Republicanos": "REPUBLICANOS",
    "Solidariedade": "SOLIDARIEDADE",
    "União": "UNIÃO",
    "UNIAO": "UNIÃO",
    "Missão": "MISSÃO",
}


def harmonizar(sigla: str | None) -> str | None:
    if not sigla or sigla.strip() == SEM_PARTIDO:
        return None
    sigla = sigla.strip()
    return SINONIMOS.get(sigla, sigla)


def sucessor_atual(sigla: str) -> str:
    """Segue a cadeia de sucessões até o partido existente hoje."""
    while sigla in SUCESSORES:
        sigla = SUCESSORES[sigla].sucessor
    return sigla
