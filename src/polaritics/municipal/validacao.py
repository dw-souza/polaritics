"""Critérios de publicação municipais (metodologia municipal, M7) e relatório.

Reaproveita o `Resultado`, a regra de publicação e o bootstrap da Câmara. Os testes que
dependem de bancadas grandes ou de referências nacionais (ordem dos partidos, Pesquisa
Legislativa Brasileira, GPS, Radar) não se aplicam.
"""

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import numpy as np
from scipy.stats import spearmanr

from polaritics import METODOLOGIA_VERSAO
from polaritics.config import DIR_PUBLICADOS
from polaritics.medidas.ideologia import irt
from polaritics.medidas.ideologia.calculo import RHAT_MAX
from polaritics.municipal import METODOLOGIA_MUNICIPAL_VERSAO
from polaritics.municipal.base import divergencias_placar
from polaritics.municipal.ideologia import VARIANTES_PUBLICADAS, preparar
from polaritics.validacao import bootstrap
from polaritics.validacao.criterios import (
    MIN_CORRELACAO_VARIANTES,
    MIN_FRACAO_ESTAVEL,
    Resultado,
    publicavel,
)
from polaritics.validacao.relatorio import ICONE, NOME_VARIANTE

MIN_VOTACOES = 30


def _diagnostico(con, municipio, legislatura, variante):
    return con.execute(
        """select n_votacoes, rhat_max, ess_min, divergencias, regua_disponivel,
                  n_grupo_esquerda, n_grupo_direita, nota_grupo_esquerda, nota_grupo_direita
           from ideologia_diagnostico where municipio = ? and legislatura = ? and variante = ?""",
        [municipio, legislatura, variante],
    ).fetchone()


def volume(con, municipio, legislatura, variante) -> Resultado:
    n = _diagnostico(con, municipio, legislatura, variante)[0]
    return Resultado(
        "Volume de dados (votações informativas)",
        variante,
        float(n),
        f"≥ {MIN_VOTACOES}",
        "aprovado" if n >= MIN_VOTACOES else "reprovado",
        "Votações nominais com ao menos 2,5% de votos na minoria.",
    )


def regua(con, municipio, legislatura, variante) -> Resultado:
    d = _diagnostico(con, municipio, legislatura, variante)
    disponivel, n_esq, n_dir, nota_esq, nota_dir = d[4:]
    detalhe = f"Grupo da esquerda: {n_esq} vereador(es)" + (
        f", nota {nota_esq:.2f}" if n_esq else ""
    )
    detalhe += f"; grupo da direita: {n_dir} vereador(es)" + (
        f", nota {nota_dir:.2f}." if n_dir else "."
    )
    return Resultado(
        "Régua por grupos-polo disponível",
        variante,
        None,
        "≥ 1 vereador em cada grupo",
        "aprovado" if disponivel else "reprovado",
        detalhe,
    )


def convergencia(con, municipio, legislatura, variante) -> Resultado:
    _, rhat, ess, div, *_ = _diagnostico(con, municipio, legislatura, variante)
    if rhat is None:
        return Resultado(
            "Convergência do MCMC (R-hat máximo)", variante, None, f"< {RHAT_MAX}",
            "reprovado", "Modelo não estimado (régua indisponível).",
        )  # fmt: skip
    return Resultado(
        "Convergência do MCMC (R-hat máximo)",
        variante,
        float(rhat),
        f"< {RHAT_MAX}",
        "aprovado" if rhat < RHAT_MAX else "reprovado",
        f"ESS mínimo {ess:.0f}; {div} divergências.",
    )


def sensibilidade_variantes(con, municipio, legislatura) -> tuple[Resultado, list[tuple]]:
    pares = con.execute(
        """select ve.nome, a.partido, a.nota, a.faixa, b.nota, b.faixa
           from ideologia a
           join ideologia b using (municipio, legislatura, id_vereador)
           join vereador ve using (municipio, id_vereador)
           where a.municipio = ? and a.legislatura = ? and a.variante = 'todas'
             and b.variante = 'merito'
           order by ve.nome""",
        [municipio, legislatura],
    ).fetchall()
    nome = "Sensibilidade: todas as votações × só mérito"
    meta = f"correlação ≥ {MIN_CORRELACAO_VARIANTES:.2f}"
    if len(pares) < 3:
        return Resultado(nome, None, None, meta, "reprovado", "Variantes não estimadas."), []
    r = float(np.corrcoef([p[2] for p in pares], [p[4] for p in pares])[0, 1])
    mudam = [p for p in pares if p[3] != p[5]]
    return (
        Resultado(
            nome,
            None,
            r,
            meta,
            "aprovado" if r >= MIN_CORRELACAO_VARIANTES else "reprovado",
            f"{len(mudam)} de {len(pares)} vereadores mudam de faixa e serão sinalizados.",
        ),
        mudam,
    )


def estabilidade(con, municipio, legislatura, variante, replicas: int) -> Resultado:
    """Bootstrap das votações (mesmo critério de D8); grava `ideologia_exibicao`."""
    nome = "Estabilidade da classificação exibida (bootstrap das votações)"
    meta = (
        f"≥ {MIN_FRACAO_ESTAVEL:.0%} dos vereadores com a classificação exibida "
        f"cobrindo ≥ {bootstrap.MIN_REPLICAS_MESMA_FAIXA:.0%} das réplicas"
    )
    m, ref = preparar(con, municipio, legislatura, variante)
    if replicas <= 0 or not ref.disponivel:
        return Resultado(nome, variante, None, meta, "pendente", "Bootstrap não executado.")
    publicada = dict(
        con.execute(
            """select id_vereador, faixa from ideologia
               where municipio = ? and legislatura = ? and variante = ?""",
            [municipio, legislatura, variante],
        ).fetchall()
    )
    faixas = bootstrap.faixas_bootstrap(m, ref, replicas)
    exibicoes = [bootstrap.exibir(publicada[d], faixas[:, i]) for i, d in enumerate(m.deputados)]
    con.execute(
        """delete from ideologia_exibicao
           where municipio = ? and legislatura = ? and variante = ?""",
        [municipio, legislatura, variante],
    )
    con.executemany(
        "insert into ideologia_exibicao values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                municipio,
                legislatura,
                variante,
                d,
                e.faixa_publicada,
                e.fracao_mesma_faixa,
                e.fronteira,
                e.rotulo,
                e.cobertura,
            )
            for d, e in zip(m.deputados, exibicoes, strict=True)
        ],
    )
    cobertos = float(
        np.mean([e.cobertura >= bootstrap.MIN_REPLICAS_MESMA_FAIXA for e in exibicoes])
    )
    return Resultado(
        nome,
        variante,
        cobertos,
        meta,
        "aprovado" if cobertos >= MIN_FRACAO_ESTAVEL else "reprovado",
        f"{replicas} réplicas com estimativa MAP; "
        f"{sum(e.fronteira for e in exibicoes)} vereadores em zona de fronteira.",
    )


def vereador_partido(con, municipio, legislatura, variante) -> Resultado:
    linhas = con.execute(
        """select i.nota, e.nota from ideologia i
           join nota_especialistas e using (partido)
           where i.municipio = ? and i.legislatura = ? and i.variante = ?""",
        [municipio, legislatura, variante],
    ).fetchall()
    rho = float(spearmanr(*zip(*linhas, strict=True)).statistic) if len(linhas) >= 3 else None
    return Resultado(
        "Vereador × nota do partido (Spearman, indicador)",
        variante,
        rho,
        "acompanhado, sem meta",
        "informativo",
        f"{len(linhas)} vereadores com partido classificado. Mede a coerência entre como o "
        "vereador vota e a classificação do partido; a diferença é um achado (M7).",
        obrigatorio=False,
    )


def peso_mocoes(con, municipio, legislatura) -> Resultado:
    """Correlação das posições (MAP) com e sem moções, nos vereadores presentes nas duas."""
    nome = "Peso das moções (correlação com e sem moções, indicador)"
    m_todas, ref_todas = preparar(con, municipio, legislatura, "todas")
    m_sem, ref_sem = preparar(con, municipio, legislatura, "sem_mocoes")
    if not (ref_todas.disponivel and ref_sem.disponivel) or m_sem.forma[1] < 2:
        return Resultado(nome, None, None, "acompanhado", "informativo", "Sem dados.", False)
    a = dict(
        zip(
            m_todas.deputados,
            irt.estimar_map(m_todas, ref_todas.esquerda, ref_todas.direita),
            strict=True,
        )
    )
    b = dict(
        zip(m_sem.deputados, irt.estimar_map(m_sem, ref_sem.esquerda, ref_sem.direita), strict=True)
    )
    comuns = sorted(a.keys() & b.keys())
    r = float(np.corrcoef([a[d] for d in comuns], [b[d] for d in comuns])[0, 1])
    n_mocoes = m_todas.forma[1] - m_sem.forma[1]
    return Resultado(
        nome,
        None,
        r,
        "acompanhado, sem meta",
        "informativo",
        f"{n_mocoes} de {m_todas.forma[1]} votações informativas são moções. "
        "Correlação baixa indica que as moções movem a posição (M3).",
        obrigatorio=False,
    )


def grupos_e_fronteira(con, municipio, legislatura, variante) -> Resultado:
    n_grupos, n, fronteira = con.execute(
        """select count(distinct i.grupo), count(*), sum(e.fronteira::int)
           from ideologia i left join ideologia_exibicao e
             using (municipio, legislatura, variante, id_vereador)
           where i.municipio = ? and i.legislatura = ? and i.variante = ?""",
        [municipio, legislatura, variante],
    ).fetchone()
    return Resultado(
        "Grupos de votação (indicador)",
        variante,
        float(n_grupos or 0),
        "acompanhado, sem meta",
        "informativo",
        f"{n} vereadores em {n_grupos} grupos distinguíveis; "
        f"{fronteira or 0} em zona de fronteira.",
        obrigatorio=False,
    )


def conferencia_placar(con, municipio) -> Resultado:
    divergentes = divergencias_placar(con, municipio)
    total = con.execute(
        """select count(distinct id_votacao) from voto where municipio = ?""", [municipio]
    ).fetchone()[0]
    exemplos = "; ".join(
        f"registro {i} ({d:%d/%m/%Y}): placar {ps}×{pn}, votos {vs}×{vn}"
        for i, d, ps, pn, vs, vn in divergentes[:5]
    )
    return Resultado(
        "Conferência do placar oficial × votos individuais (indicador)",
        None,
        float(len(divergentes)),
        "acompanhado",
        "informativo",
        f"{len(divergentes)} de {total} registros com placar diferente da soma dos votos."
        + (f" {exemplos}." if exemplos else ""),
        obrigatorio=False,
    )


def atualidade(con, municipio, legislatura) -> Resultado:
    """Última votação registrada no SAPL: câmaras às vezes param de lançar as sessões."""
    ultima, dias = con.execute(
        """select max(data), current_date - max(data) from votacao_valida
           where municipio = ? and legislatura = ?""",
        [municipio, legislatura],
    ).fetchone()
    return Resultado(
        "Atualidade dos dados (dias desde a última votação, indicador)",
        None,
        float(dias),
        "acompanhado",
        "informativo",
        f"Última votação registrada no SAPL em {ultima:%d/%m/%Y}.",
        obrigatorio=False,
    )


def avaliar(con, municipio: str, legislatura: int, replicas: int = 100):
    sensibilidade, mudam = sensibilidade_variantes(con, municipio, legislatura)
    resultados = [
        sensibilidade,
        peso_mocoes(con, municipio, legislatura),
        conferencia_placar(con, municipio),
        atualidade(con, municipio, legislatura),
    ]
    for variante in VARIANTES_PUBLICADAS:
        resultados += [
            volume(con, municipio, legislatura, variante),
            regua(con, municipio, legislatura, variante),
            convergencia(con, municipio, legislatura, variante),
            estabilidade(con, municipio, legislatura, variante, replicas),
            vereador_partido(con, municipio, legislatura, variante),
            grupos_e_fronteira(con, municipio, legislatura, variante),
        ]
    return resultados, mudam


def _valor(r: Resultado) -> str:
    if r.valor is None:
        return "—"
    if r.criterio.startswith("Estabilidade"):
        return f"{r.valor:.1%}"
    return f"{r.valor:.3f}" if r.valor % 1 else f"{r.valor:.0f}"


def _markdown(nome_municipio, legislatura, resultados, mudam, veredito, gerado_em) -> str:
    linhas = [
        f"# Validação — Câmara de {nome_municipio}, {legislatura}ª legislatura",
        "",
        f"Metodologia municipal {METODOLOGIA_MUNICIPAL_VERSAO} (sobre a geral "
        f"v{METODOLOGIA_VERSAO}) · gerado em {gerado_em:%d/%m/%Y %H:%M} UTC",
        "",
        "| Variante | Publicável |",
        "|---|---|",
        *(f"| {NOME_VARIANTE[v]} | {'✅ sim' if ok else '❌ não'} |" for v, ok in veredito.items()),
        "",
        "| | Critério | Variante | Valor | Meta | Detalhe |",
        "|---|---|---|---|---|---|",
    ]
    for r in resultados:
        obrigatorio = "" if r.obrigatorio else " *(não bloqueia)*"
        linhas.append(
            f"| {ICONE[r.status]} | {r.criterio}{obrigatorio} | {NOME_VARIANTE[r.variante]} "
            f"| {_valor(r)} | {r.meta} | {r.detalhe} |"
        )
    linhas += [
        "",
        f"## Vereadores cuja faixa muda entre as variantes ({len(mudam)})",
        "",
        "| Vereador | Partido | Todas as votações | Só mérito |",
        "|---|---|---|---|",
        *(
            f"| {nome} | {partido} | {faixa_a} ({nota_a:.1f}) | {faixa_b} ({nota_b:.1f}) |"
            for nome, partido, nota_a, faixa_a, nota_b, faixa_b in mudam
        ),
        "",
    ]
    return "\n".join(linhas)


def gerar(
    con: duckdb.DuckDBPyConnection,
    municipio: str,
    legislatura: int,
    replicas: int = 100,
    destino: Path = DIR_PUBLICADOS,
) -> dict[str, bool]:
    resultados, mudam = avaliar(con, municipio, legislatura, replicas)
    veredito = {v: publicavel(resultados, v) for v in VARIANTES_PUBLICADAS}
    gerado_em = datetime.now(UTC).replace(tzinfo=None)
    con.execute(
        "delete from validacao where municipio = ? and legislatura = ?", [municipio, legislatura]
    )
    con.executemany(
        "insert into validacao values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (municipio, legislatura, *asdict(r).values(), METODOLOGIA_MUNICIPAL_VERSAO, gerado_em)
            for r in resultados
        ],
    )
    nome = con.execute("select nome from municipio where municipio = ?", [municipio]).fetchone()[0]
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"validacao-{municipio}-{legislatura}.md").write_text(
        _markdown(nome, legislatura, resultados, mudam, veredito, gerado_em), encoding="utf-8"
    )
    return veredito


ESQUEMA_VALIDACAO = """
create table if not exists ideologia_exibicao (
    municipio varchar, legislatura integer, variante varchar, id_vereador varchar,
    faixa_publicada varchar, fracao_mesma_faixa double, fronteira boolean,
    faixa_exibida varchar, cobertura double);
create table if not exists validacao (
    municipio varchar, legislatura integer, criterio varchar, variante varchar, valor double,
    meta varchar, status varchar, detalhe varchar, obrigatorio boolean,
    versao_metodologia varchar, gerado_em timestamp);
"""
