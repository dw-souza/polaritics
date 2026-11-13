"""Cálculo completo de uma câmara municipal: base → posição → medidas → validação.

Com 15 vereadores e algumas dezenas de votações, o MCMC leva segundos. Por isso não há
arquivo separado para os resultados do modelo (como `modelo.duckdb` na Câmara): a base e os
resultados são recriados juntos a cada execução.
"""

import logging
from pathlib import Path

import duckdb

from polaritics.municipal.base import construir_base
from polaritics.municipal.config import CAMINHO_BASE_MUNICIPAL, Municipio
from polaritics.municipal.ideologia import (
    ESQUEMA_RESULTADOS,
    VARIANTES_PUBLICADAS,
    calcular_ideologia,
)
from polaritics.municipal.medidas import calcular_governismo, calcular_presenca
from polaritics.municipal.validacao import ESQUEMA_VALIDACAO, gerar

log = logging.getLogger(__name__)


def legislaturas_com_votos(con: duckdb.DuckDBPyConnection, municipio: str) -> list[int]:
    return [
        n
        for (n,) in con.execute(
            """select distinct legislatura from votacao_valida
               where municipio = ? and legislatura is not null order by 1""",
            [municipio],
        ).fetchall()
    ]


def calcular(
    municipios: list[Municipio],
    destino: Path = CAMINHO_BASE_MUNICIPAL,
    replicas: int = 100,
    **mcmc,
) -> dict[tuple[str, int], dict[str, bool]]:
    """Devolve o veredito de publicação por (município, legislatura) e variante."""
    construir_base(municipios, destino)
    vereditos = {}
    with duckdb.connect(str(destino)) as con:
        con.execute(ESQUEMA_RESULTADOS)
        con.execute(ESQUEMA_VALIDACAO)
        calcular_governismo(con)
        calcular_presenca(con)
        for m in municipios:
            for legislatura in legislaturas_com_votos(con, m.slug):
                for variante in VARIANTES_PUBLICADAS:
                    calcular_ideologia(con, m.slug, legislatura, variante, **mcmc)
                vereditos[(m.slug, legislatura)] = gerar(con, m.slug, legislatura, replicas)
    return vereditos
