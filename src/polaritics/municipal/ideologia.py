"""Posição pelos votos numa câmara municipal (metodologia municipal, M4).

O modelo é o mesmo IRT da Câmara (`medidas/ideologia/irt.py`). Mudam a régua, que é fixada
por grupos-polo em vez de partidos-polo (M4.1), e a exibição, que ganha a posição na câmara e
os grupos de votação (M4.2).
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import duckdb
import numpy as np

from polaritics.base.partidos import sucessor_atual
from polaritics.medidas.ideologia import escala, irt
from polaritics.medidas.ideologia.calculo import (
    LIMITE_DIREITA,
    LIMITE_ESQUERDA,
    MIN_MINORIA,
    MIN_PARTICIPACAO,
    RHAT_MAX,
)
from polaritics.medidas.ideologia.faixas import faixa
from polaritics.municipal import METODOLOGIA_MUNICIPAL_VERSAO

log = logging.getLogger(__name__)

# "sem_mocoes" não é publicada: serve ao indicador do peso das moções (M7).
VARIANTES = {
    "todas": "true",
    "merito": "v.tipo = 'merito'",
    "sem_mocoes": "not v.eh_mocao",
}
VARIANTES_PUBLICADAS = ("todas", "merito")
PROB_NOVO_GRUPO = 0.95


def montar_matriz(
    con: duckdb.DuckDBPyConnection, municipio: str, legislatura: int, variante: str
) -> irt.MatrizVotos:
    linhas = con.execute(
        f"""
        with votos as (
            select vt.id_vereador, vt.id_votacao, vt.voto_codificado as y
            from voto vt
            join votacao_valida v using (municipio, id_votacao)
            where v.municipio = ? and v.legislatura = ? and vt.voto_codificado is not null
              and {VARIANTES[variante]}
        ),
        informativas as (
            select id_votacao from votos group by 1
            having least(avg(y), 1 - avg(y)) >= {MIN_MINORIA}
        ),
        filtrado as (select * from votos where id_votacao in (select id_votacao from informativas)),
        participantes as (
            select id_vereador from filtrado group by 1
            having count(*) >= {MIN_PARTICIPACAO} * (select count(*) from informativas)
        )
        select id_vereador, id_votacao, y from filtrado
        where id_vereador in (select id_vereador from participantes)
        order by id_vereador, id_votacao
        """,
        [municipio, legislatura],
    ).fetchall()
    vereadores = sorted({d for d, _, _ in linhas})
    votacoes = sorted({v for _, v, _ in linhas})
    i_ver = {d: i for i, d in enumerate(vereadores)}
    i_vot = {v: i for i, v in enumerate(votacoes)}
    return irt.MatrizVotos(
        vereadores,
        votacoes,
        np.array([i_ver[d] for d, _, _ in linhas], dtype=int),
        np.array([i_vot[v] for _, v, _ in linhas], dtype=int),
        np.array([y for _, _, y in linhas], dtype=np.float32),
    )


def partido_na_legislatura(
    con: duckdb.DuckDBPyConnection, municipio: str, legislatura: int
) -> dict[str, str]:
    """Partido de cada vereador no dia do seu último voto na legislatura (M2)."""
    return dict(
        con.execute(
            """with ultimo as (
                   select vt.id_vereador, max(v.data) as dia
                   from voto vt join votacao_valida v using (municipio, id_votacao)
                   where v.municipio = ? and v.legislatura = ? and vt.voto_codificado is not null
                   group by 1
               )
               select u.id_vereador, arg_max(f.partido, f.inicio)
               from ultimo u join filiacao f
                 on f.municipio = ? and f.id_vereador = u.id_vereador and f.inicio <= u.dia
                and (f.fim is null or f.fim >= u.dia)
               group by 1""",
            [municipio, legislatura, municipio],
        ).fetchall()
    )


@dataclass(frozen=True)
class ReguaGrupos:
    """Régua linear fixada por dois grupos-polo (M4.1). Mesma interface que a régua da Câmara
    usa no bootstrap: `esquerda`, `direita` e `nota_polos`."""

    partido_ver: np.ndarray  # partido de cada vereador da matriz
    nota_partido: np.ndarray  # nota dos especialistas do partido de cada vereador (nan = sem)
    esquerda: np.ndarray  # índices do grupo-polo da esquerda
    direita: np.ndarray

    @classmethod
    def montar(cls, partido_ver: np.ndarray, notas: dict[str, float]) -> "ReguaGrupos":
        nota = np.array(
            [notas.get(sucessor_atual(p), np.nan) if p else np.nan for p in partido_ver]
        )
        return cls(
            partido_ver,
            nota,
            np.flatnonzero(nota < LIMITE_ESQUERDA),
            np.flatnonzero(nota > LIMITE_DIREITA),
        )

    @property
    def disponivel(self) -> bool:
        return len(self.esquerda) > 0 and len(self.direita) > 0

    @property
    def nota_esquerda(self) -> float:
        """Média das notas dos partidos do grupo, ponderada pelo número de vereadores."""
        return float(self.nota_partido[self.esquerda].mean())

    @property
    def nota_direita(self) -> float:
        return float(self.nota_partido[self.direita].mean())

    def nota_polos(self, theta: np.ndarray) -> np.ndarray:
        return escala.ajustar_polos(
            float(np.median(theta[self.esquerda])),
            self.nota_esquerda,
            float(np.median(theta[self.direita])),
            self.nota_direita,
        )(theta)

    def polo_unico(self) -> np.ndarray:
        """Vereador que é sozinho o seu grupo-polo: a nota dele é a do partido por construção."""
        unico = np.zeros(len(self.partido_ver), dtype=bool)
        for grupo in (self.esquerda, self.direita):
            if len(grupo) == 1:
                unico[grupo] = True
        return unico


def preparar(con, municipio: str, legislatura: int, variante: str):
    m = montar_matriz(con, municipio, legislatura, variante)
    partido = partido_na_legislatura(con, municipio, legislatura)
    notas = dict(con.execute("select partido, nota from nota_especialistas").fetchall())
    partido_ver = np.array([partido.get(d) for d in m.deputados], dtype=object)
    return m, ReguaGrupos.montar(partido_ver, notas)


def posicoes_na_camara(theta: np.ndarray) -> np.ndarray:
    """Ordem de cada vereador em cada amostra, de 1 (mais à esquerda) a N."""
    return np.argsort(np.argsort(theta, axis=1), axis=1) + 1


def grupos_de_votacao(theta: np.ndarray, prob: float = PROB_NOVO_GRUPO) -> np.ndarray:
    """Grupo de cada vereador (1 = mais à esquerda). Vizinhos na ordem pela mediana ficam no
    mesmo grupo, salvo se a probabilidade a posteriori de o da direita estar de fato à direita
    for ≥ `prob` (M4.2)."""
    ordem = np.argsort(np.median(theta, axis=0))
    grupo = np.empty(theta.shape[1], dtype=int)
    atual = 1
    grupo[ordem[0]] = atual
    for anterior, seguinte in zip(ordem[:-1], ordem[1:], strict=True):
        if np.mean(theta[:, seguinte] > theta[:, anterior]) >= prob:
            atual += 1
        grupo[seguinte] = atual
    return grupo


def calcular_ideologia(
    con: duckdb.DuckDBPyConnection, municipio: str, legislatura: int, variante: str, **mcmc
) -> bool:
    """Estima e grava as tabelas `ideologia*` da legislatura. Retorna se convergiu."""
    m, regua = preparar(con, municipio, legislatura, variante)
    if not regua.disponivel:
        log.warning(
            "%s %dª (%s): sem vereador num dos grupos-polo", municipio, legislatura, variante
        )
        _gravar_diagnostico(con, municipio, legislatura, variante, m, regua, None)
        return False
    log.info("%s %dª: matriz %s × %s, variante %s", municipio, legislatura, *m.forma, variante)
    r = irt.estimar(m, regua.esquerda, regua.direita, **mcmc)
    _gravar(con, municipio, legislatura, variante, m, regua, r)
    _gravar_diagnostico(con, municipio, legislatura, variante, m, regua, r)
    log.info("R-hat máx %.4f, ESS mín %.0f, divergências %d", r.rhat_max, r.ess_min, r.divergencias)
    return r.rhat_max < RHAT_MAX


def _gravar(con, municipio, legislatura, variante, m, regua: ReguaGrupos, r) -> None:
    notas = np.array([regua.nota_polos(theta) for theta in r.theta])
    p05, p50, p95 = np.percentile(notas, [5, 50, 95], axis=0)
    pos = posicoes_na_camara(r.theta)
    pos05, pos50, pos95 = np.percentile(pos, [5, 50, 95], axis=0, method="nearest")
    grupo = grupos_de_votacao(r.theta)
    tamanho = np.bincount(grupo)[grupo]
    theta50 = np.median(r.theta, axis=0)
    n_votos = np.bincount(m.i_dep, minlength=len(m.deputados))
    unico = regua.polo_unico()
    polo = np.full(len(m.deputados), None, dtype=object)
    polo[regua.esquerda], polo[regua.direita] = "esquerda", "direita"
    con.execute(
        "delete from ideologia where municipio = ? and legislatura = ? and variante = ?",
        [municipio, legislatura, variante],
    )
    con.executemany(
        f"insert into ideologia values ({', '.join(['?'] * 21)})",
        [
            (
                municipio,
                legislatura,
                variante,
                d,
                regua.partido_ver[i],
                int(n_votos[i]),
                float(theta50[i]),
                float(p50[i]),
                float(p05[i]),
                float(p95[i]),
                faixa(p50[i]),
                faixa(p05[i]),
                faixa(p95[i]),
                int(pos50[i]),
                int(pos05[i]),
                int(pos95[i]),
                len(m.deputados),
                int(grupo[i]),
                int(tamanho[i]),
                polo[i],
                bool(unico[i]),
            )
            for i, d in enumerate(m.deputados)
        ],
    )
    con.execute(
        "delete from ideologia_votacao where municipio = ? and legislatura = ? and variante = ?",
        [municipio, legislatura, variante],
    )
    alpha, beta = np.median(r.alpha, axis=0), np.median(r.beta, axis=0)
    con.executemany(
        "insert into ideologia_votacao values (?, ?, ?, ?, ?, ?)",
        [
            (municipio, legislatura, variante, v, float(alpha[j]), float(beta[j]))
            for j, v in enumerate(m.votacoes)
        ],
    )


def _gravar_diagnostico(con, municipio, legislatura, variante, m, regua, r) -> None:
    con.execute(
        """delete from ideologia_diagnostico
           where municipio = ? and legislatura = ? and variante = ?""",
        [municipio, legislatura, variante],
    )
    con.execute(
        f"insert into ideologia_diagnostico values ({', '.join(['?'] * 16)})",
        [
            municipio,
            legislatura,
            variante,
            *m.forma,
            len(m.y),
            None if r is None else r.rhat_max,
            None if r is None else r.ess_min,
            None if r is None else r.divergencias,
            r is not None and r.rhat_max < RHAT_MAX,
            regua.disponivel,
            len(regua.esquerda),
            len(regua.direita),
            regua.nota_esquerda if len(regua.esquerda) else None,
            regua.nota_direita if len(regua.direita) else None,
            datetime.now(UTC).replace(tzinfo=None),
        ],
    )


ESQUEMA_RESULTADOS = f"""
create table if not exists ideologia (
    municipio varchar, legislatura integer, variante varchar, id_vereador varchar,
    partido varchar, n_votos integer, theta double,
    nota double, nota_p05 double, nota_p95 double,
    faixa varchar, faixa_p05 varchar, faixa_p95 varchar,
    posicao integer, posicao_p05 integer, posicao_p95 integer, n_vereadores integer,
    grupo integer, tamanho_grupo integer,
    grupo_polo varchar,              -- esquerda | direita | null (M4.1)
    polo_unico boolean);             -- sozinho no grupo-polo: nota = do partido por construção
create table if not exists ideologia_votacao (
    municipio varchar, legislatura integer, variante varchar, id_votacao varchar,
    alpha double, beta double);
create table if not exists ideologia_diagnostico (
    municipio varchar, legislatura integer, variante varchar,
    n_vereadores integer, n_votacoes integer, n_votos integer,
    rhat_max double, ess_min double, divergencias integer, convergiu boolean,
    regua_disponivel boolean, n_grupo_esquerda integer, n_grupo_direita integer,
    nota_grupo_esquerda double, nota_grupo_direita double, calculado_em timestamp);
-- versão do anexo municipal que gerou estes resultados
create or replace view versao_metodologia as select '{METODOLOGIA_MUNICIPAL_VERSAO}' as versao;
"""
