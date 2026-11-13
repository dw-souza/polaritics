"""Carga da base municipal no Postgres de publicação (schema `municipal`).

A posição só entra para as variantes aprovadas na validação (M7). Governismo e presença são
descritivos, não dependem do modelo, e entram para toda legislatura com votos. A carga de um
município roda numa transação: ou substitui tudo, ou nada muda.
"""

import logging
from pathlib import Path

import duckdb

from polaritics import METODOLOGIA_VERSAO
from polaritics.municipal import METODOLOGIA_MUNICIPAL_VERSAO
from polaritics.municipal.config import CAMINHO_BASE_MUNICIPAL, Municipio
from polaritics.municipal.ideologia import VARIANTES_PUBLICADAS
from polaritics.publicar.neon import ErroPublicacao, _comandos, url_banco
from polaritics.validacao.criterios import Resultado, publicavel

log = logging.getLogger(__name__)

ESQUEMA_PG = Path(__file__).with_name("esquema_pg.sql")
N_VOTACOES_EXPLICATIVAS = 8
TABELAS = [
    "legislatura",
    "vereador",
    "mandato",
    "filiacao",
    "posicao",
    "governismo",
    "presenca",
    "votacao_explicativa",
    "validacao",
]


def variantes_publicaveis(con, municipio: str, legislatura: int) -> list[str]:
    linhas = con.execute(
        """select criterio, variante, valor, meta, status, detalhe, obrigatorio, gerado_em
           from validacao where municipio = ? and legislatura = ?""",
        [municipio, legislatura],
    ).fetchall()
    if not linhas:
        raise ErroPublicacao(f"{municipio} {legislatura}ª sem validação; rode `municipal calcular`")
    calculado = con.execute(
        """select max(calculado_em) from ideologia_diagnostico
           where municipio = ? and legislatura = ?""",
        [municipio, legislatura],
    ).fetchone()[0]
    if calculado and min(linha[-1] for linha in linhas) < calculado:
        raise ErroPublicacao("a validação é anterior ao último cálculo do modelo; calcule de novo")
    resultados = [Resultado(*linha[:-1]) for linha in linhas]
    return [v for v in VARIANTES_PUBLICADAS if publicavel(resultados, v)]


def _carregar(con, m: Municipio, aprovadas: dict[int, list[str]]) -> None:
    p = [m.slug]
    for tabela in TABELAS:
        con.execute(f"delete from pg.municipal.{tabela} where municipio = ?", p)
    con.execute("delete from pg.municipal.municipio where municipio = ?", p)
    con.execute("insert into pg.municipal.municipio select * from municipio where municipio = ?", p)
    con.execute(
        """insert into pg.municipal.legislatura
           select l.municipio, l.numero, l.inicio, l.fim, any_value(pf.nome),
                  any_value(pf.partido_na_posse),
                  (select count(*) from votacao_valida v
                   where v.municipio = l.municipio and v.legislatura = l.numero),
                  (select count(*) from votacao_valida v
                   where v.municipio = l.municipio and v.legislatura = l.numero
                     and (select least(count(*) filter (voto_codificado = 1),
                                       count(*) filter (voto_codificado = 0))
                          from voto vt where vt.municipio = v.municipio
                          and vt.id_votacao = v.id_votacao) >= 1)
           from legislatura l
           left join prefeito pf on pf.municipio = l.municipio and pf.inicio <= l.fim
                                and pf.fim >= l.inicio
           where l.municipio = ? group by l.municipio, l.numero, l.inicio, l.fim""",
        p,
    )
    con.execute(
        """insert into pg.municipal.vereador
           select municipio, id_vereador, nome, nome_completo, sexo, foto_url
           from vereador where municipio = ?""",
        p,
    )
    # partido do último voto na legislatura, pela filiação vigente nesse dia (M2)
    con.execute(
        """insert into pg.municipal.mandato
           with ultimo as (
               select vt.municipio, vt.id_vereador, v.legislatura, max(v.data) as dia,
                      count(*) filter (vt.voto_codificado is not null) as n_votos
               from voto vt join votacao_valida v using (municipio, id_votacao)
               where vt.municipio = ? and v.legislatura is not null
               group by all
           )
           select u.municipio, u.id_vereador, u.legislatura,
                  arg_max(f.partido, f.inicio), any_value(u.n_votos)
           from ultimo u
           left join filiacao f on f.municipio = u.municipio and f.id_vereador = u.id_vereador
                and f.inicio <= u.dia and (f.fim is null or f.fim >= u.dia)
           where u.n_votos > 0
           group by all""",
        p,
    )
    con.execute(
        """insert into pg.municipal.filiacao
           select municipio, id_vereador, partido, inicio, fim from filiacao where municipio = ?""",
        p,
    )
    for legislatura, variantes in aprovadas.items():
        if variantes:
            _carregar_posicao(con, m, legislatura, variantes)
    con.execute(
        """insert into pg.municipal.governismo
           select municipio, legislatura, id_vereador, prefeito, n_total, taxa_total,
                  n_disputadas, alinhados_disputadas, taxa_disputadas, suficiente
           from governismo where municipio = ?""",
        p,
    )
    con.execute(
        """insert into pg.municipal.presenca
           select municipio, legislatura, id_vereador, sessoes, presentes, taxa, suficiente
           from presenca_plenario where municipio = ?""",
        p,
    )
    con.execute(
        """insert into pg.municipal.validacao
           select municipio, legislatura, criterio, variante, valor, meta, status, detalhe,
                  obrigatorio, versao_metodologia, gerado_em
           from validacao where municipio = ?""",
        p,
    )
    for legislatura, variantes in aprovadas.items():
        con.execute(
            """insert into pg.municipal.publicacao
               select (select coalesce(max(id), 0) + 1 from pg.municipal.publicacao), ?, ?, ?, ?,
                      max(data), now()
               from votacao_valida where municipio = ? and legislatura = ?""",
            [
                m.slug,
                legislatura,
                f"{METODOLOGIA_VERSAO} + {METODOLOGIA_MUNICIPAL_VERSAO}",
                variantes,
                m.slug,
                legislatura,
            ],
        )


def _carregar_posicao(con, m: Municipio, legislatura: int, variantes: list[str]) -> None:
    params = [m.slug, legislatura, variantes]
    con.execute(
        """insert into pg.municipal.posicao
           select i.municipio, i.legislatura, i.variante, i.id_vereador, i.partido, i.nota,
                  i.nota_p05, i.nota_p95, i.faixa, coalesce(e.faixa_exibida, i.faixa),
                  coalesce(e.fronteira, false), i.posicao, i.posicao_p05, i.posicao_p95,
                  i.n_vereadores, i.grupo, i.tamanho_grupo, i.grupo_polo, i.polo_unico, i.n_votos
           from ideologia i
           left join ideologia_exibicao e using (municipio, legislatura, variante, id_vereador)
           where i.municipio = ? and i.legislatura = ? and list_contains(?, i.variante)""",
        params,
    )
    # Mesma regra da Câmara (metodologia, seção 6): discriminação × direção do voto, no
    # sentido da posição do vereador em relação ao centro da câmara; uma votação por matéria.
    con.execute(
        f"""insert into pg.municipal.votacao_explicativa
            with centro as (
                select variante, median(theta) as c from ideologia
                where municipio = ? and legislatura = ? group by 1
            ),
            contribuicao as (
                select i.id_vereador, i.variante, vt.id_votacao, vt.voto_original,
                       iv.beta * (2 * vt.voto_codificado - 1) * sign(i.theta - c.c) as peso
                from ideologia i
                join centro c using (variante)
                join voto vt on vt.municipio = i.municipio and vt.id_vereador = i.id_vereador
                     and vt.voto_codificado is not null
                join ideologia_votacao iv on iv.municipio = i.municipio
                     and iv.id_votacao = vt.id_votacao and iv.variante = i.variante
                     and iv.legislatura = i.legislatura
                where i.municipio = ? and i.legislatura = ? and list_contains(?, i.variante)
            ),
            uma_por_materia as (
                select c.*, v.id_materia from contribuicao c
                join votacao v on v.municipio = ? and v.id_votacao = c.id_votacao
                qualify row_number() over (
                    partition by c.id_vereador, c.variante, coalesce(v.id_materia, c.id_votacao)
                    order by c.peso desc, c.id_votacao) = 1
            ),
            ordenado as (
                select *, row_number() over (
                    partition by id_vereador, variante order by peso desc, id_votacao) as ordem
                from uma_por_materia
            )
            select ?, ?, o.variante, o.id_vereador, o.ordem, o.id_votacao, v.data,
                   mt.titulo, mt.ementa, v.tipo,
                   o.voto_original, v.placar_sim || ' × ' || v.placar_nao, o.peso, v.url
            from ordenado o
            join votacao v on v.municipio = ? and v.id_votacao = o.id_votacao
            left join materia mt on mt.municipio = v.municipio and mt.id_materia = o.id_materia
            where o.ordem <= {N_VOTACOES_EXPLICATIVAS}""",
        [m.slug, legislatura, m.slug, legislatura, variantes, m.slug, m.slug, legislatura, m.slug],
    )


def publicar(
    m: Municipio, base: Path = CAMINHO_BASE_MUNICIPAL, url: str | None = None
) -> dict[int, list[str]]:
    """Publica o município. Devolve as variantes da posição publicadas por legislatura."""
    with duckdb.connect() as con:
        con.execute("attach ? as local (read_only)", [str(base)])
        con.execute("use local")
        legislaturas = [
            n
            for (n,) in con.execute(
                """select distinct legislatura from votacao_valida
                   where municipio = ? and legislatura is not null order by 1""",
                [m.slug],
            ).fetchall()
        ]
        aprovadas = {n: variantes_publicaveis(con, m.slug, n) for n in legislaturas}
        con.execute("install postgres; load postgres;")
        con.execute("attach ? as pg (type postgres)", [url or url_banco()])
        for comando in _comandos(ESQUEMA_PG.read_text(encoding="utf-8")):
            con.execute("call postgres_execute('pg', ?)", [comando])
        con.execute("begin transaction")
        try:
            _carregar(con, m, aprovadas)
            con.execute("commit")
        except Exception:
            con.execute("rollback")
            raise
    log.info("%s publicado: %s", m.slug, aprovadas)
    return aprovadas
