"""Critérios de publicação (metodologia, seção 8). Cada função devolve um `Resultado`."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import duckdb
import numpy as np
from scipy.stats import spearmanr

from polaritics.config import DIR_BRUTOS
from polaritics.medidas.ideologia.calculo import RHAT_MAX, preparar
from polaritics.validacao import bootstrap, referencias

Status = Literal["aprovado", "reprovado", "pendente", "informativo"]

MIN_SPEARMAN_ESPECIALISTAS = 0.80
MIN_SPEARMAN_BLS = 0.75
MAX_DIFERENCA_RADAR = 0.03
MIN_CORRELACAO_VARIANTES = 0.90
MIN_FRACAO_ESTAVEL = 0.90
ARQUIVO_BLS = DIR_BRUTOS / "bls" / "BLS9_full.tab"


@dataclass(frozen=True)
class Resultado:
    criterio: str
    variante: str | None  # None = não depende da variante
    valor: float | None
    meta: str
    status: Status
    detalhe: str
    obrigatorio: bool = True


def _medianas_partidos(con, legislatura, variante):
    """Mediana da nota (visão principal) por partido com nota de especialistas e ≥ 3 deputados."""
    return con.execute(
        """select i.partido, median(i.nota), any_value(e.nota)
           from ideologia i join nota_especialistas e using (partido)
           where i.legislatura = ? and i.variante = ?
           group by 1 having count(*) >= 3 order by 2""",
        [legislatura, variante],
    ).fetchall()


def ordem_especialistas(con, legislatura, variante) -> Resultado:
    linhas = _medianas_partidos(con, legislatura, variante)
    rho = float(spearmanr([v for _, v, _ in linhas], [e for _, _, e in linhas]).statistic)
    return Resultado(
        "Ordem dos partidos × especialistas (Spearman)",
        variante,
        rho,
        f"≥ {MIN_SPEARMAN_ESPECIALISTAS:.2f}",
        "aprovado" if rho >= MIN_SPEARMAN_ESPECIALISTAS else "reprovado",
        f"{len(linhas)} partidos com nota e ≥ 3 deputados",
    )


def distancia_especialistas(con, legislatura, variante) -> Resultado:
    linhas = _medianas_partidos(con, legislatura, variante)
    r = float(np.corrcoef([v for _, v, _ in linhas], [e for _, _, e in linhas])[0, 1])
    return Resultado(
        "Distâncias × especialistas (Pearson, indicador)",
        variante,
        r,
        "acompanhado, sem meta",
        "informativo",
        "Quanto as distâncias pelos votos se parecem com as dos especialistas (decisão D7)",
        obrigatorio=False,
    )


def ordem_bls(con, legislatura, variante, arquivo: Path = ARQUIVO_BLS) -> Resultado:
    detalhe = (
        "Os dados da Pesquisa Legislativa Brasileira (Harvard Dataverse, doi:10.7910/DVN/WM9IZ8) "
        "exigem cadastro (guestbook) para download. Baixe BLS9_full.tab para data/raw/bls/."
        if not arquivo.exists()
        else "Arquivo presente; leitura ainda não implementada."
    )
    return Resultado(
        "Ordem dos partidos × Pesquisa Legislativa Brasileira (Spearman)",
        variante,
        None,
        f"≥ {MIN_SPEARMAN_BLS:.2f}",
        "pendente",
        detalhe,
        obrigatorio=False,
    )


def _familia(nota: float) -> str:
    baixo, alto = referencias.GPS_CORTES
    return "esquerda" if nota < baixo else "direita" if nota > alto else "centro"


def familias_gps(con, legislatura, variante) -> Resultado:
    linhas = [
        (p, _familia(v), referencias.GPS_FAMILIAS[p])
        for p, v, _ in _medianas_partidos(con, legislatura, variante)
        if p in referencias.GPS_FAMILIAS
    ]
    invertidos = [p for p, nossa, gps in linhas if {nossa, gps} == {"esquerda", "direita"}]
    vizinhos = [f"{p} ({nossa} × {gps})" for p, nossa, gps in linhas if nossa != gps]
    return Resultado(
        "Famílias dos partidos × GPS Partidário 2026",
        variante,
        float(len(invertidos)),
        "0 inversões esquerda ↔ direita",
        "aprovado" if not invertidos else "reprovado",
        (
            f"{len(linhas) - len(vizinhos)}/{len(linhas)} na mesma família. "
            + (f"Diferenças entre famílias vizinhas: {', '.join(vizinhos)}. " if vizinhos else "")
            + "O GPS combina cinco dimensões (votos, frentes, migração, coligações, doações); "
            "o Polaritics usa só votos, então diferenças centro × direita no centrão são "
            "esperadas (efeito governo, metodologia 5.5)."
        ),
    )


def governismo_radar(con, legislatura) -> Resultado:
    if legislatura != 57:
        return Resultado(
            "Governismo médio × Radar do Congresso",
            None,
            None,
            "—",
            "pendente",
            "Referência externa disponível só para a 57ª legislatura.",
            obrigatorio=False,
        )
    media = con.execute(
        """select avg(t) from (
               select sum(alinhados_total) / sum(n_total) as t from governismo
               where legislatura = ? and ano in (2023, 2024)
               group by id_camara having sum(n_total) >= 30)""",
        [legislatura],
    ).fetchall()[0][0]
    diferenca = media - referencias.RADAR_GOVERNISMO_2023_2024
    return Resultado(
        "Governismo médio 2023–2024 × Radar do Congresso",
        None,
        float(media),
        f"diferença ≤ {MAX_DIFERENCA_RADAR * 100:.0f} p.p. de "
        f"{referencias.RADAR_GOVERNISMO_2023_2024:.0%}",
        "aprovado" if abs(diferenca) <= MAX_DIFERENCA_RADAR else "reprovado",
        f"Diferença de {diferenca * 100:+.1f} p.p. Fonte: {referencias.RADAR_FONTE}",
    )


def sensibilidade_variantes(con, legislatura) -> tuple[Resultado, list[tuple]]:
    pares = con.execute(
        """select d.nome, a.partido, a.nota, a.faixa, b.nota, b.faixa
           from ideologia a
           join ideologia b on b.id_camara = a.id_camara and b.legislatura = a.legislatura
           join deputado d on d.id_camara = a.id_camara
           where a.legislatura = ? and a.variante = 'todas' and b.variante = 'merito'
           order by d.nome""",
        [legislatura],
    ).fetchall()
    r = float(np.corrcoef([p[2] for p in pares], [p[4] for p in pares])[0, 1])
    mudam = [p for p in pares if p[3] != p[5]]
    return (
        Resultado(
            "Sensibilidade: todas as votações × só mérito",
            None,
            r,
            f"correlação ≥ {MIN_CORRELACAO_VARIANTES:.2f}",
            "aprovado" if r >= MIN_CORRELACAO_VARIANTES else "reprovado",
            f"{len(mudam)} de {len(pares)} deputados mudam de faixa e serão sinalizados.",
        ),
        mudam,
    )


def estabilidade(con, legislatura, variante, replicas: int) -> Resultado:
    """Bootstrap das votações; grava a exibição de cada deputado em `ideologia_exibicao`."""
    meta = (
        f"≥ {MIN_FRACAO_ESTAVEL:.0%} dos deputados com a classificação exibida "
        f"(faixa ou fronteira) cobrindo ≥ {bootstrap.MIN_REPLICAS_MESMA_FAIXA:.0%} das réplicas"
    )
    nome = "Estabilidade da classificação exibida (bootstrap das votações)"
    if replicas <= 0:
        return Resultado(nome, variante, None, meta, "pendente", "Bootstrap não executado.")
    m, ref = preparar(con, legislatura, variante)
    publicada = dict(
        con.execute(
            "select id_camara, faixa from ideologia where legislatura = ? and variante = ?",
            [legislatura, variante],
        ).fetchall()
    )
    replicas_faixas = bootstrap.faixas_bootstrap(m, ref, replicas)
    exibicoes = [
        bootstrap.exibir(publicada[d], replicas_faixas[:, i]) for i, d in enumerate(m.deputados)
    ]
    _gravar_exibicao(con, legislatura, variante, m.deputados, exibicoes)
    cobertos = float(
        np.mean([e.cobertura >= bootstrap.MIN_REPLICAS_MESMA_FAIXA for e in exibicoes])
    )
    estaveis = float(np.mean([not e.fronteira for e in exibicoes]))
    return Resultado(
        nome,
        variante,
        cobertos,
        meta,
        "aprovado" if cobertos >= MIN_FRACAO_ESTAVEL else "reprovado",
        f"{replicas} réplicas com estimativa MAP. {estaveis:.1%} com faixa única estável; "
        f"{sum(e.fronteira for e in exibicoes)} deputados exibidos em zona de fronteira. "
        "Critério da v0.2 (a v0.1 exigia faixa única e reprovou; ver metodologia 4.3.1).",
    )


def _gravar_exibicao(con, legislatura, variante, deputados, exibicoes) -> None:
    con.execute("""create table if not exists ideologia_exibicao (
        id_camara varchar, legislatura integer, variante varchar, faixa_publicada varchar,
        fracao_mesma_faixa double, fronteira boolean, faixa_exibida varchar,
        cobertura double)""")
    con.execute(
        "delete from ideologia_exibicao where legislatura = ? and variante = ?",
        [legislatura, variante],
    )
    con.executemany(
        "insert into ideologia_exibicao values (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                d,
                legislatura,
                variante,
                e.faixa_publicada,
                e.fracao_mesma_faixa,
                e.fronteira,
                e.rotulo,
                e.cobertura,
            )
            for d, e in zip(deputados, exibicoes, strict=True)
        ],
    )


def fracao_fronteira(con, legislatura, variante) -> Resultado:
    linhas = con.execute(
        """select avg(fronteira::int), count(*) from ideologia_exibicao
           where legislatura = ? and variante = ?""",
        [legislatura, variante],
    ).fetchall()
    fracao, n = linhas[0] if linhas and linhas[0][1] else (None, 0)
    return Resultado(
        "Deputados em zona de fronteira (indicador)",
        variante,
        None if fracao is None else float(fracao),
        "acompanhado; teto a definir antes da 58ª legislatura",
        "informativo",
        f"{n} deputados avaliados. Mede quantos ficam perto de um corte entre faixas (4.3.1).",
        obrigatorio=False,
    )


def convergencia(con, legislatura, variante) -> Resultado:
    rhat, ess, div = con.execute(
        """select rhat_max, ess_min, divergencias from ideologia_diagnostico
           where legislatura = ? and variante = ?""",
        [legislatura, variante],
    ).fetchall()[0]
    return Resultado(
        "Convergência do MCMC (R-hat máximo)",
        variante,
        float(rhat),
        f"< {RHAT_MAX}",
        "aprovado" if rhat < RHAT_MAX else "reprovado",
        f"ESS mínimo {ess:.0f}; {div} divergências.",
    )


def avaliar(con: duckdb.DuckDBPyConnection, legislatura: int, replicas: int = 100):
    """Todos os critérios. Devolve (resultados, deputados que mudam de faixa entre variantes)."""
    resultados = [governismo_radar(con, legislatura)]
    sensibilidade, mudam = sensibilidade_variantes(con, legislatura)
    resultados.append(sensibilidade)
    for variante in ("todas", "merito"):
        resultados += [
            convergencia(con, legislatura, variante),
            ordem_especialistas(con, legislatura, variante),
            familias_gps(con, legislatura, variante),
            ordem_bls(con, legislatura, variante),
            estabilidade(con, legislatura, variante, replicas),
            fracao_fronteira(con, legislatura, variante),
            distancia_especialistas(con, legislatura, variante),
        ]
    return resultados, mudam


def publicavel(resultados: list[Resultado], variante: str) -> bool:
    """Publicável se nenhum critério obrigatório (da variante ou geral) ficou sem aprovação."""
    return all(
        r.status == "aprovado"
        for r in resultados
        if r.obrigatorio and r.variante in (variante, None)
    )
