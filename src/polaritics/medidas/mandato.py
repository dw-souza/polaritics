"""Gastos da cota, presença e atividade legislativa (metodologia, seção 11).

Todas as medidas usam só o tempo em que o deputado estava de fato em exercício (tabela
`exercicio`, do histórico oficial): suplentes e licenciados não são comparados pelos 4 anos.
"""

import duckdb

MIN_MESES = 3.0  # gastos e atividade: mínimo de meses em exercício para entrar no ranking
MIN_SESSOES = 20  # presença: mínimo de sessões deliberativas em exercício

# Situações que indicam aprovação na Câmara (a proposição seguiu adiante ou virou lei).
APROVADA_NA_CAMARA = (
    "Aguardando Apreciação pelo Senado Federal",
    "Aguardando Envio ao Senado Federal",
    "Aguardando Autógrafos na Mesa",
    "Aguardando Sanção",
    "Aguardando Apreciação do Veto",
    "Transformado em Norma Jurídica",
)
VIROU_LEI = "Transformado em Norma Jurídica"


def calcular_gastos(con: duckdb.DuckDBPyConnection, legislatura: int) -> None:
    """Tabelas `gastos` (por deputado × período), `gastos_categoria` e `gastos_fornecedor`.

    Meses em exercício são proporcionais aos dias de cada mês (Ato da Mesa 43/2009, art. 11),
    até o último mês com dados de cota. O ranking usa o gasto mensal dividido pela cota do
    estado (`relativo`), porque a cota de Roraima é 40% maior que a do DF.
    """
    con.execute(
        f"""
        create or replace table gastos as
        with fim_dados as (select max(make_date(ano, mes, 1)) as mes from despesa),
        meses as (
            select unnest(generate_series(date_trunc('month', l.inicio)::date,
                                          (select mes from fim_dados), interval 1 month))::date
                   as mes
            from legislatura l where l.numero = $1
        ),
        cal as (select mes, last_day(mes) as fim_mes, day(last_day(mes)) as dias from meses),
        exposicao as (
            select e.id_camara, c.mes,
                   least(1.0, sum(datediff('day', greatest(e.inicio, c.mes),
                                           least(e.fim, c.fim_mes)) + 1) / any_value(c.dias))
                       as fracao
            from exercicio e join cal c on e.inicio <= c.fim_mes and e.fim >= c.mes
            where e.legislatura = $1
            group by all
        ),
        gasto_mes as (
            select id_camara, make_date(ano, mes, 1) as mes, sum(valor) as valor, mode(uf) as uf
            from despesa where make_date(ano, mes, 1) in (select mes from cal)
            group by all
        ),
        junto as (
            select coalesce(x.id_camara, g.id_camara) as id_camara,
                   coalesce(x.mes, g.mes) as mes,
                   coalesce(x.fracao, 0) as fracao, coalesce(g.valor, 0) as valor, g.uf
            from exposicao x full join gasto_mes g using (id_camara, mes)
        ),
        agregado as (
            select id_camara, year(mes) as ano, sum(fracao) as meses, sum(valor) as total,
                   mode(uf) as uf
            from junto
            group by grouping sets ((id_camara), (id_camara, year(mes)))
        )
        select a.id_camara, $1 as legislatura, a.ano, a.uf, a.meses, a.total,
               a.total / nullif(a.meses, 0) as por_mes,
               a.total / nullif(a.meses, 0) / c.valor as relativo,
               a.meses >= {MIN_MESES} and c.valor is not null as suficiente
        from agregado a left join cota_uf c using (uf)
        """,
        [legislatura],
    )
    con.execute(
        """
        create or replace table gastos_categoria as
        select d.id_camara, $1 as legislatura, d.categoria, sum(d.valor) as valor
        from despesa d join legislatura l on l.numero = $1
         and make_date(d.ano, d.mes, 1) between date_trunc('month', l.inicio) and l.fim
        group by all
        """,
        [legislatura],
    )
    # Fornecedor pessoa física (CPF, 11 dígitos) não é identificado pelo nome.
    con.execute(
        """
        create or replace table gastos_fornecedor as
        with por_fornecedor as (
            select id_camara,
                   case when length(cnpj_cpf) = 11 then 'Pessoa física' else fornecedor end
                       as fornecedor,
                   case when length(cnpj_cpf) = 11 then null else cnpj_cpf end as cnpj,
                   sum(valor) as valor
            from despesa d join legislatura l on l.numero = $1
             and make_date(d.ano, d.mes, 1) between date_trunc('month', l.inicio) and l.fim
            group by all
        )
        select id_camara, $1 as legislatura, fornecedor, cnpj, valor
        from por_fornecedor
        qualify row_number() over (partition by id_camara order by valor desc) <= 5
        """,
        [legislatura],
    )


def calcular_presenca(con: duckdb.DuckDBPyConnection, legislatura: int) -> None:
    """Tabela `presenca_plenario`: sessões deliberativas em que o deputado estava em exercício
    e quantas tiveram presença registrada."""
    con.execute(
        f"""
        create or replace table presenca_plenario as
        with em_exercicio as (
            select distinct e.id_camara, s.id as id_sessao, s.data
            from exercicio e join sessao s on s.data between e.inicio and e.fim
            where e.legislatura = $1
        ),
        marcado as (
            select x.*, p.id_sessao is not null as presente
            from em_exercicio x
            left join presenca p on p.id_sessao = x.id_sessao and p.id_camara = x.id_camara
        )
        select id_camara, $1 as legislatura, year(data) as ano, count(*) as sessoes,
               count(*) filter (presente) as presentes,
               count(*) filter (presente) / count(*) as taxa,
               count(*) >= {MIN_SESSOES} as suficiente
        from marcado
        group by grouping sets ((id_camara), (id_camara, year(data)))
        """,
        [legislatura],
    )


def calcular_atividade(con: duckdb.DuckDBPyConnection, legislatura: int) -> None:
    """Tabela `atividade`: PL, PLP, PEC e PDL apresentados como primeiro autor durante a
    legislatura, quantos foram aprovados na Câmara e quantos viraram lei."""
    aprovadas = ", ".join(f"'{s}'" for s in APROVADA_NA_CAMARA)
    con.execute(
        f"""
        create or replace table atividade as
        with autor as (
            select a.id_camara, p.*
            from autoria a join proposicao p on p.id = a.id_proposicao
            join legislatura l on l.numero = $1
             and p.ano between year(l.inicio) and year(l.fim)
            where a.ordem = 1 and a.proponente
        ),
        meses as (
            select id_camara, meses from gastos where legislatura = $1 and ano is null
        )
        select id_camara, $1 as legislatura,
               count(a.id) as apresentados,
               count(a.id) filter (where a.situacao in ({aprovadas})) as aprovados_camara,
               count(a.id) filter (where a.situacao = '{VIROU_LEI}') as viraram_lei,
               coalesce(any_value(m.meses), 0) >= {MIN_MESES} as suficiente
        from autor a full join meses m using (id_camara)
        group by 1
        """,
        [legislatura],
    )
    con.execute(
        f"""
        create or replace table atividade_aprovadas as
        select a.id_camara, $1 as legislatura, p.id, p.sigla_tipo, p.numero, p.ano, p.ementa,
               p.situacao
        from autoria a join proposicao p on p.id = a.id_proposicao
        join legislatura l on l.numero = $1 and p.ano between year(l.inicio) and year(l.fim)
        where a.ordem = 1 and a.proponente and p.situacao in ({aprovadas})
        """,
        [legislatura],
    )
