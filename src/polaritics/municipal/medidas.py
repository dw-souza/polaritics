"""Governismo (M5) e presença (M6) numa câmara municipal."""

import duckdb

from polaritics.municipal.base import TIPOS_PROJETO

# Governismo exibido com ao menos este número de votações disputadas em que o vereador votou.
MIN_DISPUTADAS = 5
# Presença calculada para quem teve ao menos este número de sessões durante o mandato.
MIN_SESSOES = 20
TIPOS_SESSAO_PRESENCA = ("Sessão Ordinária", "Sessão Extraordinária")


def calcular_governismo(con: duckdb.DuckDBPyConnection) -> None:
    """Voto Sim nos projetos de autoria do prefeito. Disputada = ao menos um voto Não."""
    tipos = ", ".join(f"'{t}'" for t in TIPOS_PROJETO)
    con.execute(f"""
        create or replace table governismo as
        with projeto as (
            select v.municipio, v.id_votacao, v.legislatura, p.nome as prefeito,
                   exists (select 1 from voto x where x.municipio = v.municipio
                           and x.id_votacao = v.id_votacao and x.voto_codificado = 0) as disputada
            from votacao_valida v
            join materia mt using (municipio, id_materia)
            join prefeito p on p.municipio = v.municipio and v.data between p.inicio and p.fim
            where mt.do_executivo and mt.sigla_tipo in ({tipos})
        )
        select p.municipio, vt.id_vereador, p.legislatura, p.prefeito,
               count(*) as n_total,
               avg(vt.voto_codificado) as taxa_total,
               count(*) filter (p.disputada) as n_disputadas,
               sum(vt.voto_codificado) filter (p.disputada) as alinhados_disputadas,
               avg(vt.voto_codificado) filter (p.disputada) as taxa_disputadas,
               count(*) filter (p.disputada) >= {MIN_DISPUTADAS} as suficiente
        from projeto p
        join voto vt using (municipio, id_votacao)
        where vt.voto_codificado is not null
        group by all
    """)


def calcular_presenca(con: duckdb.DuckDBPyConnection) -> None:
    """Sessões ordinárias e extraordinárias com lista de presença registrada, durante o
    mandato do vereador na legislatura."""
    tipos = ", ".join(f"'{t}'" for t in TIPOS_SESSAO_PRESENCA)
    con.execute(f"""
        create or replace table presenca_plenario as
        with realizada as (
            select s.municipio, s.id_sessao, s.data, l.numero as legislatura
            from sessao s
            join legislatura l on l.municipio = s.municipio and s.data between l.inicio and l.fim
            where s.tipo in ({tipos})
              and exists (select 1 from presenca p where p.municipio = s.municipio
                          and p.id_sessao = s.id_sessao)
        )
        select m.municipio, m.id_vereador, r.legislatura,
               count(*) as sessoes,
               count(p.id_vereador) as presentes,
               count(p.id_vereador) / count(*) as taxa,
               count(*) >= {MIN_SESSOES} as suficiente
        from mandato m
        join realizada r on r.municipio = m.municipio and r.legislatura = m.legislatura
                        and r.data between m.inicio and m.fim
        left join (select distinct * from presenca) p
               on p.municipio = r.municipio and p.id_sessao = r.id_sessao
              and p.id_vereador = m.id_vereador
        group by all
    """)
