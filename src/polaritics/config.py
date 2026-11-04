"""Parâmetros fixos: legislaturas, governos e caminhos de dados.

Uma nova legislatura ou um novo governo entra aqui, sem mudança no restante do código.
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DIR_DADOS = RAIZ / "data"
DIR_BRUTOS = DIR_DADOS / "raw"
DIR_PROCESSADOS = DIR_DADOS / "processed"
DIR_PUBLICADOS = DIR_DADOS / "published"


@dataclass(frozen=True)
class Periodo:
    inicio: date
    fim: date

    def contem(self, dia: date) -> bool:
        return self.inicio <= dia <= self.fim

    @property
    def anos(self) -> list[int]:
        return list(range(self.inicio.year, self.fim.year + 1))


@dataclass(frozen=True)
class Legislatura:
    numero: int
    periodo: Periodo


@dataclass(frozen=True)
class Governo:
    esfera: str  # "federal"; no futuro, "estadual:SP", "municipal:3550308" etc.
    chefe: str
    partido_na_posse: str
    periodo: Periodo


LEGISLATURAS = {
    56: Legislatura(56, Periodo(date(2019, 2, 1), date(2023, 1, 31))),
    57: Legislatura(57, Periodo(date(2023, 2, 1), date(2027, 1, 31))),
}

GOVERNOS = [
    Governo("federal", "Jair Bolsonaro", "PSL", Periodo(date(2019, 1, 1), date(2022, 12, 31))),
    Governo(
        "federal", "Luiz Inácio Lula da Silva", "PT", Periodo(date(2023, 1, 1), date(2026, 12, 31))
    ),
]


def governo_em(dia: date, esfera: str = "federal") -> Governo | None:
    """Governo em exercício na data (o governismo é sempre relativo a ele)."""
    return next((g for g in GOVERNOS if g.esfera == esfera and g.periodo.contem(dia)), None)
