"""Governismo (metodologia, seção 5.2).

Percentual de votos iguais à orientação da liderança do Governo, só em votações em que o
Governo orientou Sim, Não ou Obstrução (obstrução conta como Não; "Liberado" fica de fora).
Ausências e abstenções do deputado não entram no denominador.

Dois números: total e em votações disputadas (orientação do Governo ≠ da Oposição). O
governismo é sempre relativo ao governo em exercício na data da votação.
"""

import duckdb

# Para ser exibido: participação mínima nas votações orientadas do período (mesma regra da
# posição ideológica) e um mínimo absoluto de votações disputadas.
MIN_PARTICIPACAO = 0.10
MIN_VOTACOES_DISPUTADAS = 30


def calcular_governismo(con: duckdb.DuckDBPyConnection) -> None:
    """Cria a tabela `governismo`: uma linha por deputado × governo, e por ano (ano não nulo)."""
    con.execute(f"""
        create or replace table governismo as
        with orientada as (
            select v.id, v.legislatura, year(v.data) as ano, g.chefe as governo,
                   og.orientacao_codificada as gov,
                   coalesce(oo.orientacao_codificada is not null
                            and oo.orientacao_codificada <> og.orientacao_codificada,
                            false) as disputada
            from votacao_valida v
            join governo g on g.esfera = 'federal' and v.data between g.inicio and g.fim
            join orientacao og on og.id_votacao = v.id and og.bancada = 'Governo'
            left join orientacao oo on oo.id_votacao = v.id and oo.bancada = 'Oposição'
            where og.orientacao_codificada is not null
        ),
        universo as (
            select legislatura, governo, ano, count(*) as votacoes_orientadas
            from orientada
            group by grouping sets ((legislatura, governo), (legislatura, governo, ano))
        ),
        pares as (
            select o.*, vt.id_camara, (vt.voto_codificado = o.gov)::int as alinhado
            from orientada o
            join voto vt on vt.id_votacao = o.id and vt.voto_codificado is not null
        ),
        agregado as (
            select id_camara, legislatura, governo, ano,
                   count(*) as n_total,
                   sum(alinhado) as alinhados_total,
                   sum(alinhado) / count(*) as taxa_total,
                   count(*) filter (disputada) as n_disputadas,
                   sum(alinhado) filter (disputada) as alinhados_disputadas,
                   sum(alinhado) filter (disputada) / count(*) filter (disputada)
                       as taxa_disputadas
            from pares
            group by grouping sets ((id_camara, legislatura, governo),
                                    (id_camara, legislatura, governo, ano))
        )
        select a.*,
               a.n_total >= {MIN_PARTICIPACAO} * u.votacoes_orientadas
                   and a.n_disputadas >= {MIN_VOTACOES_DISPUTADAS} as suficiente
        from agregado a
        join universo u on u.legislatura = a.legislatura and u.governo = a.governo
                       and u.ano is not distinct from a.ano
    """)
