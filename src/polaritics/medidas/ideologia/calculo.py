"""Orquestra a posição ideológica: matriz de votos → IRT → escala 0–10 → faixas → tabelas."""

import logging
from datetime import UTC, datetime

import duckdb
import numpy as np

from polaritics import METODOLOGIA_VERSAO
from polaritics.medidas.ideologia import escala, irt
from polaritics.medidas.ideologia.faixas import faixa

log = logging.getLogger(__name__)

VARIANTES = {"todas": "true", "merito": "v.tipo = 'merito'"}
MIN_MINORIA = 0.025  # votações quase unânimes não informam posição
MIN_PARTICIPACAO = 0.10
MIN_DEPUTADOS_ANCORA = 3
LIMITE_ESQUERDA, LIMITE_DIREITA = 4.5, 5.5  # notas que definem os grupos de referência do sinal
RHAT_MAX = 1.01


def montar_matriz(con: duckdb.DuckDBPyConnection, legislatura: int, variante: str):
    linhas = con.execute(
        f"""
        with votos as (
            select vt.id_camara, vt.id_votacao, vt.voto_codificado as y
            from voto vt join votacao_valida v on v.id = vt.id_votacao
            where v.legislatura = ? and vt.voto_codificado is not null and {VARIANTES[variante]}
        ),
        informativas as (
            select id_votacao from votos group by 1
            having least(avg(y), 1 - avg(y)) >= {MIN_MINORIA}
        ),
        filtrado as (select * from votos where id_votacao in (select id_votacao from informativas)),
        participantes as (
            select id_camara from filtrado group by 1
            having count(*) >= {MIN_PARTICIPACAO} * (select count(*) from informativas)
        )
        select id_camara, id_votacao, y from filtrado
        where id_camara in (select id_camara from participantes)
        order by id_camara, id_votacao
        """,
        [legislatura],
    ).fetchall()
    deputados = sorted({d for d, _, _ in linhas})
    votacoes = sorted({v for _, v, _ in linhas})
    i_dep = {d: i for i, d in enumerate(deputados)}
    i_vot = {v: i for i, v in enumerate(votacoes)}
    return irt.MatrizVotos(
        deputados,
        votacoes,
        np.array([i_dep[d] for d, _, _ in linhas]),
        np.array([i_vot[v] for _, v, _ in linhas]),
        np.array([y for _, _, y in linhas], dtype=np.float32),
    )


def partido_na_legislatura(con: duckdb.DuckDBPyConnection, legislatura: int) -> dict[str, str]:
    """Partido mais recente de cada deputado na legislatura (último voto registrado)."""
    return dict(
        con.execute(
            """select f.id_camara, arg_max(f.partido, f.fim)
               from filiacao f join legislatura l on f.inicio between l.inicio and l.fim
               where l.numero = ? and f.partido is not null group by 1""",
            [legislatura],
        ).fetchall()
    )


def calcular_ideologia(
    con: duckdb.DuckDBPyConnection, legislatura: int, variante: str = "todas", **mcmc
) -> bool:
    """Estima e grava as tabelas `ideologia*`. Retorna se o modelo convergiu."""
    m = montar_matriz(con, legislatura, variante)
    partido = partido_na_legislatura(con, legislatura)
    notas = dict(con.execute("select partido, nota from nota_especialistas").fetchall())
    partido_dep = np.array([partido.get(d) for d in m.deputados], dtype=object)
    nota_dep = np.array([notas.get(p, np.nan) for p in partido_dep], dtype=float)
    esquerda = np.flatnonzero(nota_dep < LIMITE_ESQUERDA)
    direita = np.flatnonzero(nota_dep > LIMITE_DIREITA)
    log.info("matriz %s × %s (%s votos), variante %s", *m.forma, len(m.y), variante)

    r = irt.estimar(m, esquerda, direita, **mcmc)

    r = irt.estimar(m, esquerda, direita, **mcmc)

    contagem = {p: int((partido_dep == p).sum()) for p in set(partido_dep) if p}
    referencias = sorted(p for p, n in contagem.items() if p in notas and n >= MIN_DEPUTADOS_ANCORA)
    polo_esq = max((p for p in referencias if notas[p] < LIMITE_ESQUERDA), key=contagem.get)
    polo_dir = max((p for p in referencias if notas[p] > LIMITE_DIREITA), key=contagem.get)
    membros = {p: np.flatnonzero(partido_dep == p) for p in referencias}
    pesos = np.array([contagem[p] for p in referencias], dtype=float)
    alvo = np.array([notas[p] for p in referencias])

    nota_voto = np.empty_like(r.theta)  # visão principal: régua fixada pelos dois polos
    nota_campo = np.empty_like(r.theta)  # visão secundária: partidos na nota dos especialistas
    for k, theta in enumerate(r.theta):
        mediana = {p: np.median(theta[idx]) for p, idx in membros.items()}
        nota_voto[k] = escala.ajustar_polos(
            mediana[polo_esq], notas[polo_esq], mediana[polo_dir], notas[polo_dir]
        )(theta)
        medianas = np.array([mediana[p] for p in referencias])
        nota_campo[k] = escala.ajustar(medianas, alvo, pesos)(theta)

    _gravar(con, legislatura, variante, m, partido_dep, r, nota_voto, nota_campo)
    _gravar_diagnostico(con, legislatura, variante, m, r, (polo_esq, polo_dir), referencias)
    log.info("R-hat máx %.4f, ESS mín %.0f, divergências %d", r.rhat_max, r.ess_min, r.divergencias)
    return r.rhat_max < RHAT_MAX


def _resumo(amostras: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    p05, p50, p95 = np.percentile(amostras, [5, 50, 95], axis=0)
    return p50, p05, p95


def _gravar(con, legislatura, variante, m, partido_dep, r, nota_voto, nota_campo):
    voto50, voto05, voto95 = _resumo(nota_voto)
    campo50, campo05, campo95 = _resumo(nota_campo)
    theta50 = np.median(r.theta, axis=0)
    n_votos = np.bincount(m.i_dep, minlength=len(m.deputados))
    con.execute("""create table if not exists ideologia (
        id_camara varchar, legislatura integer, variante varchar, partido varchar,
        n_votos integer, theta double,
        nota double, nota_p05 double, nota_p95 double,
        faixa varchar, faixa_p05 varchar, faixa_p95 varchar,
        nota_campo double, nota_campo_p05 double, nota_campo_p95 double)""")
    con.execute(
        "delete from ideologia where legislatura = ? and variante = ?", [legislatura, variante]
    )
    con.executemany(
        "insert into ideologia values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                d,
                legislatura,
                variante,
                partido_dep[i],
                int(n_votos[i]),
                float(theta50[i]),
                float(voto50[i]),
                float(voto05[i]),
                float(voto95[i]),
                faixa(voto50[i]),
                faixa(voto05[i]),
                faixa(voto95[i]),
                float(campo50[i]),
                float(campo05[i]),
                float(campo95[i]),
            )
            for i, d in enumerate(m.deputados)
        ],
    )
    con.execute("""create table if not exists ideologia_votacao (
        id_votacao varchar, legislatura integer, variante varchar,
        alpha double, beta double)""")
    con.execute(
        "delete from ideologia_votacao where legislatura = ? and variante = ?",
        [legislatura, variante],
    )
    alpha50, beta50 = np.median(r.alpha, axis=0), np.median(r.beta, axis=0)
    con.executemany(
        "insert into ideologia_votacao values (?, ?, ?, ?, ?)",
        [
            (v, legislatura, variante, float(alpha50[j]), float(beta50[j]))
            for j, v in enumerate(m.votacoes)
        ],
    )


def _gravar_diagnostico(con, legislatura, variante, m, r, polos, referencias):
    con.execute("""create table if not exists ideologia_diagnostico (
        legislatura integer, variante varchar, n_deputados integer, n_votacoes integer,
        n_votos integer, rhat_max double, ess_min double, divergencias integer,
        convergiu boolean, polos varchar, partidos_referencia varchar,
        versao_metodologia varchar, calculado_em timestamp)""")
    con.execute(
        "delete from ideologia_diagnostico where legislatura = ? and variante = ?",
        [legislatura, variante],
    )
    con.execute(
        "insert into ideologia_diagnostico values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            legislatura,
            variante,
            *m.forma,
            len(m.y),
            r.rhat_max,
            r.ess_min,
            r.divergencias,
            r.rhat_max < RHAT_MAX,
            ",".join(polos),
            ",".join(referencias),
            METODOLOGIA_VERSAO,
            datetime.now(UTC).replace(tzinfo=None),
        ],
    )
