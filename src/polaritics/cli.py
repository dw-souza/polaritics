"""Linha de comando: `uv run polaritics <comando>`."""

import argparse
import logging
from datetime import date

import duckdb

from polaritics.base.carga import CAMINHO_BASE, construir_base
from polaritics.base.conexao import conectar
from polaritics.coleta import especialistas
from polaritics.coleta.camara import ColetorCamara, checar_sanidade
from polaritics.config import LEGISLATURAS
from polaritics.medidas.fidelidade import calcular_fidelidade
from polaritics.medidas.governismo import calcular_governismo
from polaritics.medidas.ideologia import irt
from polaritics.medidas.ideologia.calculo import VARIANTES, calcular_ideologia
from polaritics.medidas.mandato import calcular_atividade, calcular_gastos, calcular_presenca
from polaritics.municipal import pipeline
from polaritics.municipal import publicar as publicar_municipal
from polaritics.municipal.coleta import ColetorSAPL
from polaritics.municipal.config import MUNICIPIOS
from polaritics.publicar import neon
from polaritics.validacao import relatorio


def coletar(args: argparse.Namespace) -> None:
    hoje = date.today()
    coletor = ColetorCamara()
    coletor.coletar(args.legislatura, hoje=hoje, forcar=args.forcar)
    contagem = checar_sanidade(coletor.destino, args.legislatura, hoje)
    for ano, n in contagem.items():
        print(f"{ano}: {n} votações nominais de plenário")
    especialistas.baixar()


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
        calcular_gastos(con, args.legislatura)
        calcular_presenca(con, args.legislatura)
        calcular_atividade(con, args.legislatura)
        media = con.execute(
            """select count(*), avg(taxa_total), avg(taxa_disputadas) from governismo
               where ano is null and suficiente and legislatura = ?""",
            [args.legislatura],
        ).fetchall()[0]
        print(f"Deputados com dados suficientes: {media[0]}")
        print(f"Governismo médio: total {media[1]:.1%} | disputadas {media[2]:.1%}")
        con.sql(RESUMO_PARTIDOS, params=[args.legislatura]).show(max_rows=40)


def ideologia(args: argparse.Namespace) -> None:
    irt.habilitar_cadeias_paralelas(args.cadeias)
    with conectar() as con:
        for variante in args.variante:
            convergiu = calcular_ideologia(
                con,
                args.legislatura,
                variante,
                aquecimento=args.aquecimento,
                amostras=args.amostras,
                cadeias=args.cadeias,
            )
            print(f"{variante}: {'convergiu' if convergiu else 'NÃO convergiu (não publicar)'}")


def validar(args: argparse.Namespace) -> None:
    with conectar() as con:
        veredito = relatorio.gerar(con, args.legislatura, replicas=args.replicas)
    for variante, ok in veredito.items():
        print(f"{variante}: {'publicável' if ok else 'NÃO publicável'}")
    print(f"relatório em data/published/validacao-{args.legislatura}.md")


def publicar(args: argparse.Namespace) -> None:
    variantes = neon.publicar(args.legislatura)
    print(f"publicado no Postgres: legislatura {args.legislatura} ({', '.join(variantes)})")


def municipal_coletar(args: argparse.Namespace) -> None:
    if not especialistas.ARQUIVO.exists():
        especialistas.baixar()
    for slug in args.municipio:
        contagem = ColetorSAPL(MUNICIPIOS[slug]).coletar()
        print(
            f"{slug}: {contagem['votoparlamentar']} votos, {contagem['registrovotacao']} votações"
        )


def municipal_calcular(args: argparse.Namespace) -> None:
    irt.habilitar_cadeias_paralelas(args.cadeias)
    vereditos = pipeline.calcular(
        [MUNICIPIOS[s] for s in args.municipio], replicas=args.replicas, cadeias=args.cadeias
    )
    for (slug, legislatura), veredito in vereditos.items():
        situacao = ", ".join(
            f"{v}: {'publicável' if ok else 'NÃO publicável'}" for v, ok in veredito.items()
        )
        print(f"{slug} {legislatura}ª — {situacao}")
        print(f"  relatório em data/published/validacao-{slug}-{legislatura}.md")


def municipal_publicar(args: argparse.Namespace) -> None:
    for slug in args.municipio:
        publicadas = publicar_municipal.publicar(MUNICIPIOS[slug])
        for legislatura, variantes in publicadas.items():
            posicao = ", ".join(variantes) if variantes else "posição não aprovada"
            print(f"{slug} {legislatura}ª publicada: governismo, presença; {posicao}")


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

    p = sub.add_parser("ideologia", help="estima a posição ideológica (IRT, MCMC)")
    p.add_argument("--legislatura", type=int, choices=sorted(LEGISLATURAS), default=57)
    p.add_argument("--variante", nargs="+", choices=sorted(VARIANTES), default=["todas", "merito"])
    p.add_argument("--aquecimento", type=int, default=1000)
    p.add_argument("--amostras", type=int, default=1000)
    p.add_argument("--cadeias", type=int, default=2)
    p.set_defaults(func=ideologia)

    p = sub.add_parser("validar", help="aplica os critérios de publicação e gera o relatório")
    p.add_argument("--legislatura", type=int, choices=sorted(LEGISLATURAS), default=57)
    p.add_argument("--replicas", type=int, default=100, help="réplicas do bootstrap (0 = pular)")
    p.set_defaults(func=validar)

    p = sub.add_parser("publicar", help="publica os resultados validados no Postgres (Neon)")
    p.add_argument("--legislatura", type=int, choices=sorted(LEGISLATURAS), default=57)
    p.set_defaults(func=publicar)

    p = sub.add_parser("base", help="constrói a base DuckDB a partir dos dados brutos")
    p.set_defaults(func=base)

    p = sub.add_parser("municipal", help="câmaras municipais (SAPL)")
    sub_mun = p.add_subparsers(required=True)
    q = sub_mun.add_parser("coletar", help="baixa os dados do SAPL da câmara")
    q.add_argument("--municipio", nargs="+", choices=sorted(MUNICIPIOS), default=sorted(MUNICIPIOS))
    q.set_defaults(func=municipal_coletar)
    q = sub_mun.add_parser("calcular", help="base, posição, medidas e validação (~1 min)")
    q.add_argument("--municipio", nargs="+", choices=sorted(MUNICIPIOS), default=sorted(MUNICIPIOS))
    q.add_argument("--replicas", type=int, default=100, help="réplicas do bootstrap")
    q.add_argument("--cadeias", type=int, default=2)
    q.set_defaults(func=municipal_calcular)
    q = sub_mun.add_parser("publicar", help="publica os resultados validados no Postgres")
    q.add_argument("--municipio", nargs="+", choices=sorted(MUNICIPIOS), default=sorted(MUNICIPIOS))
    q.set_defaults(func=municipal_publicar)

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # uma linha por requisição no SAPL
    args.func(args)


if __name__ == "__main__":
    main()
