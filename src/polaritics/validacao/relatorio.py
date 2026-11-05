"""Relatório de validação: grava a tabela `validacao` e um Markdown em data/published/."""

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from polaritics import METODOLOGIA_VERSAO
from polaritics.config import DIR_PUBLICADOS
from polaritics.validacao.criterios import Resultado, avaliar, publicavel

ICONE = {"aprovado": "✅", "reprovado": "❌", "pendente": "⏳", "informativo": "ℹ️"}
NOME_VARIANTE = {"todas": "Todas as votações", "merito": "Só mérito", None: "Geral"}


PERCENTUAIS = ("Governismo", "Estabilidade", "Deputados em zona")


def _valor(r: Resultado) -> str:
    if r.valor is None:
        return "—"
    if r.criterio.startswith(PERCENTUAIS):
        return f"{r.valor:.1%}"
    return f"{r.valor:.3f}" if r.valor % 1 else f"{r.valor:.0f}"


def _markdown(legislatura, resultados, mudam, veredito, gerado_em) -> str:
    linhas = [
        f"# Validação — {legislatura}ª legislatura",
        "",
        f"Metodologia v{METODOLOGIA_VERSAO} · gerado em {gerado_em:%d/%m/%Y %H:%M} UTC",
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
        f"## Deputados cuja faixa muda entre as variantes ({len(mudam)})",
        "",
        "Na página de cada um, a tela avisa que a faixa depende da visão escolhida.",
        "",
        "| Deputado | Partido | Todas as votações | Só mérito |",
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
    legislatura: int,
    replicas: int = 100,
    destino: Path = DIR_PUBLICADOS,
) -> dict[str, bool]:
    resultados, mudam = avaliar(con, legislatura, replicas)
    veredito = {v: publicavel(resultados, v) for v in ("todas", "merito")}
    gerado_em = datetime.now(UTC).replace(tzinfo=None)

    con.execute("""create table if not exists modelo.validacao (
        legislatura integer, criterio varchar, variante varchar, valor double, meta varchar,
        status varchar, detalhe varchar, obrigatorio boolean, versao_metodologia varchar,
        gerado_em timestamp)""")
    con.execute("delete from modelo.validacao where legislatura = ?", [legislatura])
    con.executemany(
        "insert into modelo.validacao values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(legislatura, *asdict(r).values(), METODOLOGIA_VERSAO, gerado_em) for r in resultados],
    )
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"validacao-{legislatura}.md").write_text(
        _markdown(legislatura, resultados, mudam, veredito, gerado_em), encoding="utf-8"
    )
    return veredito
