"""Conexão com a base (dados) e o arquivo do modelo (resultados caros de recalcular).

A base é recriada do zero a cada `polaritics base`; os resultados do modelo de ideologia e da
validação ficam em `modelo.duckdb` e sobrevivem a isso. A conexão anexa os dois e as consultas
encontram as tabelas sem prefixo (search_path); quem grava resultados do modelo usa o prefixo
`modelo.` explicitamente.
"""

from pathlib import Path

import duckdb

from polaritics.config import DIR_PROCESSADOS

CAMINHO_BASE = DIR_PROCESSADOS / "polaritics.duckdb"
CAMINHO_MODELO = DIR_PROCESSADOS / "modelo.duckdb"
MODELO = "modelo"


def anexar_modelo(
    con: duckdb.DuckDBPyConnection,
    catalogo_base: str,
    modelo: Path = CAMINHO_MODELO,
    somente_leitura: bool = False,
) -> None:
    modo = " (read_only)" if somente_leitura else ""
    modelo.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"attach ? as {MODELO}{modo}", [str(modelo)])
    con.execute(f"set search_path = '{catalogo_base},{MODELO}'")


def conectar(
    base: Path = CAMINHO_BASE, modelo: Path = CAMINHO_MODELO, somente_leitura: bool = False
) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(base), read_only=somente_leitura)
    catalogo = con.execute("select current_database()").fetchall()[0][0]
    anexar_modelo(con, catalogo, modelo, somente_leitura)
    return con
