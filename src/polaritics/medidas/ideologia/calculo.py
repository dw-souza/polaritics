"""Orquestra a posição ideológica: matriz de votos → IRT → escala 0–10 → faixas → tabelas."""

import hashlib
import logging
from dataclasses import dataclass
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


@dataclass(frozen=True)
class Referencias:
    """Partidos de referência da régua: polos (visão principal) e todos com nota (secundária)."""

    partido_dep: np.ndarray  # partido de cada deputado da matriz
    notas: dict[str, float]  # nota dos especialistas por partido
    referencias: list[str]  # partidos com nota e ≥ MIN_DEPUTADOS_ANCORA deputados
    polos: tuple[str, str]  # maior partido de cada polo
    membros: dict[str, np.ndarray]
    pesos: np.ndarray

    @classmethod
    def montar(cls, partido_dep: np.ndarray, notas: dict[str, float]) -> "Referencias":
        contagem = {p: int((partido_dep == p).sum()) for p in set(partido_dep) if p}
        referencias = sorted(
            p for p, n in contagem.items() if p in notas and n >= MIN_DEPUTADOS_ANCORA
        )
        polo_esq = max((p for p in referencias if notas[p] < LIMITE_ESQUERDA), key=contagem.get)
        polo_dir = max((p for p in referencias if notas[p] > LIMITE_DIREITA), key=contagem.get)
        return cls(
            partido_dep,
            notas,
            referencias,
            (polo_esq, polo_dir),
            {p: np.flatnonzero(partido_dep == p) for p in referencias},
            np.array([contagem[p] for p in referencias], dtype=float),
        )

    @property
    def esquerda(self) -> np.ndarray:
        """Deputados de partidos classificados abaixo de 4,5 (fixam o sinal do modelo)."""
        return self._por_nota(lambda n: n < LIMITE_ESQUERDA)

    @property
    def direita(self) -> np.ndarray:
        return self._por_nota(lambda n: n > LIMITE_DIREITA)

    def _por_nota(self, condicao) -> np.ndarray:
        return np.flatnonzero(
            [p in self.notas and condicao(self.notas[p]) for p in self.partido_dep]
        )

    def nota_polos(self, theta: np.ndarray) -> np.ndarray:
        """Visão principal: régua linear fixada pelos dois partidos-polo."""
        esq, dir_ = self.polos
        return escala.ajustar_polos(
            np.median(theta[self.membros[esq]]),
            self.notas[esq],
            np.median(theta[self.membros[dir_]]),
            self.notas[dir_],
        )(theta)

    def nota_campo(self, theta: np.ndarray) -> np.ndarray:
        """Visão secundária: cada partido perto da própria nota de especialistas."""
        medianas = np.array([np.median(theta[self.membros[p]]) for p in self.referencias])
        alvo = np.array([self.notas[p] for p in self.referencias])
        return escala.ajustar(medianas, alvo, self.pesos)(theta)


def preparar(con: duckdb.DuckDBPyConnection, legislatura: int, variante: str):
    """Matriz de votos e referências da régua para a legislatura e variante."""
    m = montar_matriz(con, legislatura, variante)
    partido = partido_na_legislatura(con, legislatura)
    notas = dict(con.execute("select partido, nota from nota_especialistas").fetchall())
    partido_dep = np.array([partido.get(d) for d in m.deputados], dtype=object)
    return m, Referencias.montar(partido_dep, notas)


def calcular_ideologia(
    con: duckdb.DuckDBPyConnection, legislatura: int, variante: str = "todas", **mcmc
) -> bool:
    """Estima e grava as tabelas `ideologia*`. Retorna se o modelo convergiu."""
    m, ref = preparar(con, legislatura, variante)
    log.info("matriz %s × %s (%s votos), variante %s", *m.forma, len(m.y), variante)

    r = irt.estimar(m, ref.esquerda, ref.direita, **mcmc)
    nota_voto = np.array([ref.nota_polos(theta) for theta in r.theta])
    nota_campo = np.array([ref.nota_campo(theta) for theta in r.theta])

    _gravar(con, legislatura, variante, m, ref.partido_dep, r, nota_voto, nota_campo)
    _gravar_diagnostico(con, legislatura, variante, m, r, ref)
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
    con.execute("""create table if not exists modelo.ideologia (
        id_camara varchar, legislatura integer, variante varchar, partido varchar,
        n_votos integer, theta double,
        nota double, nota_p05 double, nota_p95 double,
        faixa varchar, faixa_p05 varchar, faixa_p95 varchar,
        nota_campo double, nota_campo_p05 double, nota_campo_p95 double)""")
    con.execute(
        "delete from modelo.ideologia where legislatura = ? and variante = ?",
        [legislatura, variante],
    )
    con.executemany(
        "insert into modelo.ideologia values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
    con.execute("""create table if not exists modelo.ideologia_votacao (
        id_votacao varchar, legislatura integer, variante varchar,
        alpha double, beta double)""")
    con.execute(
        "delete from modelo.ideologia_votacao where legislatura = ? and variante = ?",
        [legislatura, variante],
    )
    alpha50, beta50 = np.median(r.alpha, axis=0), np.median(r.beta, axis=0)
    con.executemany(
        "insert into modelo.ideologia_votacao values (?, ?, ?, ?, ?)",
        [
            (v, legislatura, variante, float(alpha50[j]), float(beta50[j]))
            for j, v in enumerate(m.votacoes)
        ],
    )


def impressao(m: irt.MatrizVotos, ref: Referencias) -> str:
    """Hash dos dados de entrada do modelo (votos, votações, partidos e notas). Se a base for
    reconstruída com os mesmos votos, a impressão não muda e o modelo continua válido."""
    h = hashlib.sha256()
    for parte in (m.deputados, m.votacoes, list(ref.partido_dep), sorted(ref.notas.items())):
        h.update(repr(parte).encode())
    for arr in (m.i_dep, m.i_vot, m.y):
        h.update(np.ascontiguousarray(arr).tobytes())
    return h.hexdigest()


def _gravar_diagnostico(con, legislatura, variante, m, r, ref):
    con.execute("""create table if not exists modelo.ideologia_diagnostico (
        legislatura integer, variante varchar, n_deputados integer, n_votacoes integer,
        n_votos integer, rhat_max double, ess_min double, divergencias integer,
        convergiu boolean, polos varchar, partidos_referencia varchar,
        versao_metodologia varchar, calculado_em timestamp, impressao varchar)""")
    con.execute(
        "delete from modelo.ideologia_diagnostico where legislatura = ? and variante = ?",
        [legislatura, variante],
    )
    con.execute(
        f"insert into modelo.ideologia_diagnostico values ({', '.join(['?'] * 14)})",
        [
            legislatura,
            variante,
            *m.forma,
            len(m.y),
            r.rhat_max,
            r.ess_min,
            r.divergencias,
            r.rhat_max < RHAT_MAX,
            ",".join(ref.polos),
            ",".join(ref.referencias),
            METODOLOGIA_VERSAO,
            datetime.now(UTC).replace(tzinfo=None),
            impressao(m, ref),
        ],
    )
