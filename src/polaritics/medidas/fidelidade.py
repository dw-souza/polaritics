"""Fidelidade partidária (metodologia, seção 5.3).

Percentual de votos iguais ao da maioria da bancada do próprio partido (na data do voto),
calculada sem o próprio deputado. Só bancadas com ao menos `MIN_BANCADA` votos Sim/Não
na votação; empates da maioria ficam de fora. Sem partido não entra.
"""

import duckdb

MIN_BANCADA = 3
# Para ser exibida: mesma regra de participação do governismo e da posição ideológica.
MIN_PARTICIPACAO = 0.10
MIN_VOTACOES = 30


def calcular_fidelidade(con: duckdb.DuckDBPyConnection) -> None:
    """Cria a tabela `fidelidade`: uma linha por deputado × legislatura, e por ano."""
    con.execute(f"""
        create or replace table fidelidade as
        with universo as (
            select legislatura, year(data) as ano, count(*) as votacoes
            from votacao_valida
            group by grouping sets ((legislatura), (legislatura, year(data)))
        ),
        votos as (
            select vt.id_votacao, vt.id_camara, vt.partido, vt.voto_codificado as y,
                   v.legislatura, year(v.data) as ano
            from voto vt join votacao_valida v on v.id = vt.id_votacao
            where vt.voto_codificado is not null and vt.partido is not null
        ),
        bancada as (
            select id_votacao, partido, count(*) as n, sum(y) as sim
            from votos group by all
        ),
        comparado as (
            select v.*,
                   case when 2 * (b.sim - v.y) > b.n - 1 then 1
                        when 2 * (b.sim - v.y) < b.n - 1 then 0 end as maioria_outros
            from votos v join bancada b using (id_votacao, partido)
            where b.n >= {MIN_BANCADA}
        ),
        agregado as (
            select id_camara, legislatura, ano,
                   count(maioria_outros) as n,
                   sum((y = maioria_outros)::int) as alinhados,
                   sum((y = maioria_outros)::int) / count(maioria_outros) as taxa
            from comparado
            group by grouping sets ((id_camara, legislatura), (id_camara, legislatura, ano))
        )
        select a.*,
               a.n >= {MIN_PARTICIPACAO} * u.votacoes and a.n >= {MIN_VOTACOES} as suficiente
        from agregado a
        join universo u on u.legislatura = a.legislatura and u.ano is not distinct from a.ano
    """)
