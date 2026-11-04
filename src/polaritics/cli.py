"""Linha de comando: `uv run polaritics <comando>`."""

import argparse
import logging
from datetime import date

import duckdb

from polaritics.base.carga import CAMINHO_BASE, construir_base
from polaritics.coleta.camara import ColetorCamara, checar_sanidade
from polaritics.config import LEGISLATURAS
from polaritics.medidas.fidelidade import calcular_fidelidade
from polaritics.medidas.governismo import calcular_governismo


def coletar(args: argparse.Namespace) -> None:
    hoje = date.today()
    coletor = ColetorCamara()
    coletor.coletar(args.legislatura, hoje=hoje, forcar=args.forcar)
    contagem = checar_sanidade(coletor.destino, args.legislatura, hoje)
    for ano, n in contagem.items():
        print(f"{ano}: {n} votações nominais de plenário")


def base(_args: argparse.Namespace) -> None:
    print(f"base construída em {construir_base()}")


RESUMO_PARTIDOS = """
    with ultimo_partido as (
        select id_camara, arg_max(partido, fim) as partido from filiacao group by 1
    )
    select coalesce(p.partido, 'sem partido') as partido, count(*) as deputados,
           round(100 * median(g.taxa_total), 1) as governismo_total,
           round(100 * median(g.taxa_disputadas), 1) as governismo_disputadas,
           round(100 * median(f.taxa), 1) as fidelidade
    from governismo g
    join ultimo_partido p using (id_camara)
    left join fidelidade f on f.id_camara = g.id_camara and f.legislatura = g.legislatura
                          and f.ano is null and f.suficiente
    where g.ano is null and g.suficiente and g.legislatura = ?
    group by all order by governismo_disputadas
"""


def medidas(args: argparse.Namespace) -> None:
    with duckdb.connect(str(CAMINHO_BASE)) as con:
        calcular_governismo(con)
        calcular_fidelidade(con)
        media = con.execute(
            """select count(*), avg(taxa_total), avg(taxa_disputadas) from governismo
               where ano is null and suficiente and legislatura = ?""",
            [args.legislatura],
        ).fetchall()[0]
        print(f"Deputados com dados suficientes: {media[0]}")
        print(f"Governismo médio: total {media[1]:.1%} | disputadas {media[2]:.1%}")
        con.sql(RESUMO_PARTIDOS, params=[args.legislatura]).show(max_rows=40)


def main() -> None:
    parser = argparse.ArgumentParser(prog="polaritics")
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("coletar", help="baixa os arquivos em lote da Câmara")
    p.add_argument("--legislatura", type=int, choices=sorted(LEGISLATURAS), default=57)
    p.add_argument("--forcar", action="store_true", help="baixa de novo também anos encerrados")
    p.set_defaults(func=coletar)

    p = sub.add_parser("medidas", help="calcula governismo e fidelidade partidária")
    p.add_argument("--legislatura", type=int, choices=sorted(LEGISLATURAS), default=57)
    p.set_defaults(func=medidas)

    p = sub.add_parser("base", help="constrói a base DuckDB a partir dos dados brutos")
    p.set_defaults(func=base)

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args.func(args)


if __name__ == "__main__":
    main()
