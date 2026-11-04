"""Siglas partidárias: harmonização e sucessões (fusões e incorporações)."""

from datetime import date

SEM_PARTIDO = "S.PART."

# Partido extinto → (sucessor, data da decisão do TSE que aprovou a fusão/incorporação).
SUCESSORES = {
    "PROS": ("SOLIDARIEDADE", date(2023, 2, 14)),
    "PSC": ("PODE", date(2023, 6, 15)),
    "PATRIOTA": ("PRD", date(2023, 11, 9)),
    "PTB": ("PRD", date(2023, 11, 9)),
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
        sigla = SUCESSORES[sigla][0]
    return sigla
