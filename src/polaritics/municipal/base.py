"""Constrói a base municipal (DuckDB) a partir dos JSON do SAPL. Sempre recria do zero."""

import json
import logging
import re
from pathlib import Path

import duckdb

from polaritics.base.partidos import harmonizar
from polaritics.coleta import especialistas
from polaritics.config import DIR_BRUTOS
from polaritics.municipal.config import CAMINHO_BASE_MUNICIPAL, Municipio

log = logging.getLogger(__name__)

ESQUEMA = Path(__file__).with_name("esquema.sql")

# Siglas usadas pelo SAPL (inclusive de partidos já extintos) → sigla dos especialistas.
SIGLAS_SAPL = {
    "REP": "REPUBLICANOS",
    "PRB": "REPUBLICANOS",
    "CID": "CIDADANIA",
    "PPS": "CIDADANIA",
    "SD": "SOLIDARIEDADE",
    "PMDB": "MDB",
    "PR": "PL",
    "DEM": "UNIÃO",  # fusão de DEM e PSL (TSE, 08/02/2022)
    "PSL": "UNIÃO",
    "PSDC": "DC",
    "PTdoB": "AVANTE",
    "PEN": "PATRIOTA",
    "PHS": "PODE",  # incorporado ao Podemos (2019)
    "PRP": "PATRIOTA",  # incorporado ao Patriota (2019)
    "PPL": "PCdoB",  # incorporado ao PCdoB (2019)
}

# Tipos de matéria cuja votação é de procedimento (metodologia municipal, M3).
TIPOS_PROCEDIMENTO = {"Req", "RU", "ATA", "RF"}
# Tipos de matéria em que o voto Sim acompanha o autor (governismo, M5).
TIPOS_PROJETO = {"PLO", "PLC", "PELOM", "PDL"}


def sigla_partido(sigla_sapl: str) -> str:
    sigla = harmonizar(sigla_sapl) or sigla_sapl
    return SIGLAS_SAPL.get(sigla, sigla)


def url_publica(url: str | None, municipio: Municipio) -> str | None:
    """O SAPL devolve links com o host interno (ex.: sapl.dmz...); troca pelo endereço público."""
    if not url:
        return None
    return re.sub(r"^https?://[^/]+", municipio.sapl, url)


def _ler(brutos: Path, nome: str) -> list[dict]:
    return json.loads((brutos / f"{nome}.json").read_text(encoding="utf-8"))


def _json(brutos: Path, nome: str) -> str:
    """Leitura direta pelo DuckDB, para os arquivos grandes (votos, matérias)."""
    return f"read_json_auto('{brutos / f'{nome}.json'}', maximum_object_size=1000000000)"


def _carregar_municipio(con, m: Municipio, brutos: Path) -> None:
    con.execute("insert into municipio values (?, ?, ?, ?)", [m.slug, m.nome, m.uf, m.sapl])
    con.executemany(
        "insert into prefeito values (?, ?, ?, ?, ?)",
        [
            (m.slug, p.nome, p.partido_na_posse, p.periodo.inicio, p.periodo.fim)
            for p in m.prefeitos
        ],
    )
    legislaturas = {r["id"]: r for r in _ler(brutos, "legislatura")}
    con.executemany(
        "insert into legislatura values (?, ?, ?, ?)",
        [(m.slug, r["numero"], r["data_inicio"], r["data_fim"]) for r in legislaturas.values()],
    )
    con.executemany(
        "insert into vereador values (?, ?, ?, ?, ?, ?)",
        [
            (
                m.slug,
                str(r["id"]),
                r["nome_parlamentar"],
                r.get("nome_completo") or None,
                r.get("sexo") or None,
                url_publica(r.get("fotografia"), m),
            )
            for r in _ler(brutos, "parlamentar")
        ],
    )
    con.executemany(
        "insert into mandato values (?, ?, ?, ?, ?, ?)",
        [
            (
                m.slug,
                str(r["parlamentar"]),
                legislaturas[r["legislatura"]]["numero"],
                r["data_inicio_mandato"],
                r["data_fim_mandato"],
                r.get("titular"),
            )
            for r in _ler(brutos, "mandato")
        ],
    )
    partidos = {r["id"]: r["sigla"] for r in _ler(brutos, "partido")}
    con.executemany(
        "insert into filiacao values (?, ?, ?, ?, ?, ?)",
        [
            (
                m.slug,
                str(r["parlamentar"]),
                partidos[r["partido"]],
                sigla_partido(partidos[r["partido"]]),
                r["data"],
                r.get("data_desfiliacao"),
            )
            for r in _ler(brutos, "filiacao")
        ],
    )


def _carregar_materias(con, m: Municipio, brutos: Path) -> None:
    tipos_autor = {r["id"]: r.get("descricao") or r["__str__"] for r in _ler(brutos, "tipoautor")}
    executivo = {
        r["id"]
        for r in _ler(brutos, "autor")
        if "executivo" in tipos_autor.get(r["tipo"], "").lower()
    }
    if not executivo:
        raise ValueError(f"{m.slug}: nenhum autor do tipo chefe do Executivo no SAPL")
    con.execute(
        f"""
        insert into materia
        select ?, m.id::varchar, t.sigla, t.descricao, m.numero, m.ano,
               nullif(trim(m.ementa), ''), list_has_any(m.autores, ?::bigint[])
        from {_json(brutos, "materia")} m
        left join {_json(brutos, "tipomateria")} t on t.id = m.tipo
        """,
        [m.slug, sorted(executivo)],
    )


def _carregar_votacoes(con, m: Municipio, brutos: Path) -> None:
    # data local da votação, como registrada (o horário vem com o fuso de Brasília)
    con.execute(
        f"""
        create temp table registro as
        select ?::varchar as municipio, id::varchar as id_votacao,
               left(data_hora::varchar, 10)::date as data, materia::varchar as id_materia,
               numero_votos_sim as placar_sim, numero_votos_nao as placar_nao
        from {_json(brutos, "registrovotacao")}
        """,
        [m.slug],
    )
    procedimento = ", ".join(f"'{t}'" for t in TIPOS_PROCEDIMENTO)
    con.execute(f"""
        insert into votacao
        select r.municipio, r.id_votacao, r.data, l.numero, r.id_materia, r.placar_sim,
               r.placar_nao,
               case when mt.sigla_tipo in ({procedimento}) then 'procedimento' else 'merito' end,
               coalesce(lower(mt.tipo) like 'moção%', false)
        from registro r
        left join materia mt on mt.municipio = r.municipio and mt.id_materia = r.id_materia
        left join legislatura l on l.municipio = r.municipio and r.data between l.inicio and l.fim
    """)
    # um voto por vereador e votação; se o SAPL tiver registro repetido, vale o mais recente
    con.execute(
        f"""
        insert into voto
        select ?, votacao::varchar, parlamentar::varchar, voto,
               case voto when 'Sim' then 1 when 'Não' then 0 end
        from {_json(brutos, "votoparlamentar")}
        qualify row_number() over (partition by votacao, parlamentar order by id desc) = 1
        """,
        [m.slug],
    )


def _carregar_presenca(con, m: Municipio, brutos: Path) -> None:
    tipos = {r["id"]: r["nome"] for r in _ler(brutos, "tiposessao")}
    con.executemany(
        "insert into sessao values (?, ?, ?, ?)",
        [
            (m.slug, str(r["id"]), r["data_inicio"], tipos.get(r["tipo"]))
            for r in _ler(brutos, "sessao")
            if r.get("finalizada")
        ],
    )
    con.executemany(
        "insert into presenca values (?, ?, ?)",
        [
            (m.slug, str(r["sessao_plenaria"]), str(r["parlamentar"]))
            for r in _ler(brutos, "presenca")
        ],
    )


def _carregar_especialistas(con, arquivo: Path) -> None:
    if not arquivo.exists():
        log.warning("notas dos especialistas ausentes (%s); rode `municipal coletar`", arquivo)
        return
    con.executemany(
        "insert into nota_especialistas values (?, ?, ?)",
        [(n.partido, n.nota, n.origem) for n in especialistas.notas_2022(arquivo)],
    )


def divergencias_placar(con, municipio: str) -> list[tuple]:
    """Registros em que o placar oficial não bate com a soma dos votos individuais."""
    return con.execute(
        """select v.id_votacao, v.data, v.placar_sim, v.placar_nao,
                  count(*) filter (vt.voto_codificado = 1), count(*) filter (vt.voto_codificado = 0)
           from votacao v join voto vt using (municipio, id_votacao)
           where v.municipio = ?
           group by all
           having v.placar_sim <> count(*) filter (vt.voto_codificado = 1)
               or v.placar_nao <> count(*) filter (vt.voto_codificado = 0)
           order by v.data""",
        [municipio],
    ).fetchall()


def construir_base(
    municipios: list[Municipio],
    destino: Path = CAMINHO_BASE_MUNICIPAL,
    arquivo_especialistas: Path = especialistas.ARQUIVO,
    raiz_brutos: Path = DIR_BRUTOS / "municipal",
) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(".duckdb.construindo")
    temporario.unlink(missing_ok=True)
    with duckdb.connect(str(temporario)) as con:
        con.execute(ESQUEMA.read_text(encoding="utf-8"))
        _carregar_especialistas(con, arquivo_especialistas)
        for m in municipios:
            brutos = raiz_brutos / m.slug
            _carregar_municipio(con, m, brutos)
            _carregar_materias(con, m, brutos)
            _carregar_votacoes(con, m, brutos)
            _carregar_presenca(con, m, brutos)
    temporario.replace(destino)
    log.info("base municipal construída em %s", destino)
    return destino
