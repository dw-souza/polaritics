"""Constrói a base DuckDB a partir dos arquivos brutos. Sempre recria do zero (idempotente)."""

import logging
from pathlib import Path

import duckdb

from polaritics.base import partidos, votacoes
from polaritics.config import DIR_BRUTOS, DIR_PROCESSADOS, GOVERNOS, LEGISLATURAS

log = logging.getLogger(__name__)

ESQUEMA = Path(__file__).with_name("esquema.sql")
CAMINHO_BASE = DIR_PROCESSADOS / "polaritics.duckdb"


def _csv(diretorio: Path, nome: str) -> str:
    padrao = diretorio / f"{nome}.csv"
    return f"read_csv('{padrao}', delim=';', header=true, all_varchar=true, union_by_name=true)"


def _registrar_funcoes(con: duckdb.DuckDBPyConnection) -> None:
    con.create_function("classificar_votacao", votacoes.classificar_votacao, [str], str)
    con.create_function("eh_nominal", votacoes.eh_nominal, [str], bool)
    con.create_function(
        "codificar_voto", votacoes.codificar_voto, [str], "TINYINT", null_handling="special"
    )
    con.create_function(
        "harmonizar_partido", partidos.harmonizar, [str], str, null_handling="special"
    )


def _carregar_referencias(con: duckdb.DuckDBPyConnection) -> None:
    con.executemany(
        "insert into legislatura values (?, ?, ?)",
        [(n, leg.periodo.inicio, leg.periodo.fim) for n, leg in LEGISLATURAS.items()],
    )
    con.executemany(
        "insert into governo values (?, ?, ?, ?, ?)",
        [
            (g.esfera, g.chefe, g.partido_na_posse, g.periodo.inicio, g.periodo.fim)
            for g in GOVERNOS
        ],
    )
    con.executemany(
        "insert into partido_sucessao values (?, ?, ?)",
        [(sigla, suc, dia) for sigla, (suc, dia) in partidos.SUCESSORES.items()],
    )


def _carregar_camara(con: duckdb.DuckDBPyConnection, brutos: Path) -> None:
    con.execute(f"""
        insert into deputado
        select regexp_extract(uri, '(\\d+)$', 1), nome, nullif(nomeCivil, ''), nullif(cpf, ''),
               nullif(siglaSexo, ''), try_cast(dataNascimento as date)
        from {_csv(brutos, "deputados")}
        where try_cast(idLegislaturaFinal as integer) >= {min(LEGISLATURAS)}
    """)
    con.execute(f"""
        insert into votacao
        select v.id, 'camara', cast(v.data as date), try_cast(v.dataHoraRegistro as timestamp),
               v.siglaOrgao, v.descricao, eh_nominal(v.descricao), false,
               classificar_votacao(v.descricao), l.numero
        from {_csv(brutos, "votacoes-*")} v
        left join legislatura l on cast(v.data as date) between l.inicio and l.fim
    """)
    con.execute(f"""
        insert into voto
        select idVotacao, deputado_id, try_cast(dataHoraVoto as timestamp), nullif(voto, ''),
               codificar_voto(nullif(voto, '')), deputado_siglaPartido,
               harmonizar_partido(deputado_siglaPartido), deputado_siglaUf
        from {_csv(brutos, "votacoesVotos-*")}
        where idVotacao in (select id from votacao)
        qualify row_number() over (
            partition by idVotacao, deputado_id order by dataHoraVoto desc) = 1
    """)
    # Nominal com placar mas sem voto individual: votação secreta (eleições, indicações) ou
    # registro duplicado da mesma votação sob outro id, cujos votos ficam no registro principal.
    con.execute("""
        update votacao set sem_votos_individuais = true
        where nominal and id not in (
            select id_votacao from voto where voto_original is not null)
    """)
    con.execute(f"""
        insert into orientacao
        select idVotacao, siglaBancada, nullif(orientacao, ''),
               codificar_voto(nullif(orientacao, ''))
        from {_csv(brutos, "votacoesOrientacoes-*")}
        where idVotacao in (select id from votacao)
        qualify row_number() over (partition by idVotacao, siglaBancada order by orientacao) = 1
    """)


def _derivar_filiacao(con: duckdb.DuckDBPyConnection) -> None:
    # Votos consecutivos com o mesmo partido viram um período de filiação. A ordem inclui
    # id_votacao para desempatar votos registrados no mesmo segundo.
    con.execute("""
        insert into filiacao
        with ordenado as (
            select id_camara, partido, data_hora, id_votacao, cast(data_hora as date) dia,
                   partido is distinct from lag(partido) over w as mudou
            from voto where data_hora is not null
            window w as (partition by id_camara order by data_hora, id_votacao)
        ),
        periodos as (
            select *, sum(mudou::int) over (
                partition by id_camara order by data_hora, id_votacao rows unbounded preceding
            ) periodo
            from ordenado
        )
        select id_camara, any_value(partido), min(dia), max(dia)
        from periodos group by id_camara, periodo
    """)


def construir_base(brutos: Path = DIR_BRUTOS / "camara", destino: Path = CAMINHO_BASE) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(".duckdb.construindo")
    temporario.unlink(missing_ok=True)
    with duckdb.connect(str(temporario)) as con:
        con.execute(ESQUEMA.read_text(encoding="utf-8"))
        _registrar_funcoes(con)
        _carregar_referencias(con)
        _carregar_camara(con, brutos)
        _derivar_filiacao(con)
    temporario.replace(destino)
    log.info("base construída em %s", destino)
    return destino
