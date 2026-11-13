"""Câmaras municipais acompanhadas. Uma nova câmara com SAPL entra aqui, sem mudar o código."""

from dataclasses import dataclass
from datetime import date

from polaritics.config import DIR_BRUTOS, DIR_PROCESSADOS, Periodo


@dataclass(frozen=True)
class Prefeito:
    nome: str
    partido_na_posse: str
    periodo: Periodo


@dataclass(frozen=True)
class Municipio:
    slug: str
    nome: str
    uf: str
    sapl: str  # endereço público do SAPL, sem barra final
    prefeitos: tuple[Prefeito, ...]

    @property
    def esfera(self) -> str:
        return f"municipal:{self.slug}"

    @property
    def dir_brutos(self):
        return DIR_BRUTOS / "municipal" / self.slug


MUNICIPIOS = {
    "franca": Municipio(
        "franca",
        "Franca",
        "SP",
        "https://sapl.franca.sp.leg.br",
        (
            Prefeito("Alexandre Ferreira", "MDB", Periodo(date(2021, 1, 1), date(2024, 12, 31))),
            Prefeito("Alexandre Ferreira", "MDB", Periodo(date(2025, 1, 1), date(2028, 12, 31))),
        ),
    ),
}

CAMINHO_BASE_MUNICIPAL = DIR_PROCESSADOS / "municipal.duckdb"
