"""Carga da base local (DuckDB) no Postgres de publicação, pela extensão `postgres` do DuckDB.

Só entram variantes aprovadas na validação (seção 8), e a validação precisa ser posterior ao
último cálculo do modelo. A carga de uma legislatura roda numa transação: ou substitui tudo,
ou nada muda.
"""

import logging
import os
from pathlib import Path

import duckdb

from polaritics import METODOLOGIA_VERSAO
from polaritics.base.carga import CAMINHO_BASE
from polaritics.config import RAIZ
from polaritics.medidas.ideologia.faixas import faixa
from polaritics.validacao.criterios import Resultado, publicavel

log = logging.getLogger(__name__)

ESQUEMA_PG = Path(__file__).with_name("esquema_pg.sql")
VARIAVEL_URL = "POLARITICS_DATABASE_URL"  # conexão direta (unpooled)
N_VOTACOES_EXPLICATIVAS = 8
URL_VOTACAO = "https://dadosabertos.camara.leg.br/api/v2/votacoes/"
URL_PROPOSICAO = "https://www.camara.leg.br/propostas-legislativas/"
URL_FOTO = "https://www.camara.leg.br/internet/deputado/bandep/"
TABELAS_POR_LEGISLATURA = [
    "posicao",
    "posicao_partido",
    "mandato",
    "governismo",
    "fidelidade",
    "votacao_explicativa",
    "validacao",
]


class ErroPublicacao(RuntimeError):
    pass


def url_banco(arquivo_env: Path = RAIZ / ".env") -> str:
    """URL do Postgres: variável de ambiente ou, se ausente, o arquivo .env local."""
    if url := os.environ.get(VARIAVEL_URL):
        return url
    if arquivo_env.exists():
        for linha in arquivo_env.read_text(encoding="utf-8").splitlines():
            chave, _, valor = linha.partition("=")
            valor = valor.split(" #", 1)[0].strip().strip("'\"")  # comentário no fim da linha
            if chave.strip() == VARIAVEL_URL and valor:
                return valor
    raise ErroPublicacao(f"defina {VARIAVEL_URL} (no ambiente ou em .env)")


def _comandos(sql: str) -> list[str]:
    """Separa o script em comandos (o Postgres não aceita vários num statement preparado)."""
    sem_comentarios = "\n".join(linha.split("--", 1)[0] for linha in sql.splitlines())
    return [c.strip() for c in sem_comentarios.split(";") if c.strip()]


def variantes_publicaveis(con: duckdb.DuckDBPyConnection, legislatura: int) -> list[str]:
    linhas = con.execute(
        """select criterio, variante, valor, meta, status, detalhe, obrigatorio, gerado_em
           from validacao where legislatura = ?""",
        [legislatura],
    ).fetchall()
    if not linhas:
        raise ErroPublicacao("sem validação para a legislatura; rode `polaritics validar`")
    calculado = con.execute(
        "select max(calculado_em) from ideologia_diagnostico where legislatura = ?", [legislatura]
    ).fetchall()[0][0]
    if min(linha[-1] for linha in linhas) < calculado:
        raise ErroPublicacao("a validação é anterior ao último cálculo do modelo; valide de novo")
    resultados = [Resultado(*linha[:-1]) for linha in linhas]
    return [v for v in ("todas", "merito") if publicavel(resultados, v)]


def _carregar(con: duckdb.DuckDBPyConnection, legislatura: int, variantes: list[str]) -> None:
    p = [legislatura]
    con.execute("delete from pg.publicado.partido")
    con.execute("""insert into pg.publicado.partido
                   select partido, nota, origem from nota_especialistas""")
    con.execute("delete from pg.publicado.deputado")
    con.execute(f"""insert into pg.publicado.deputado
                    select id_camara, nome, nome_civil, sexo, '{URL_FOTO}' || id_camara || '.jpg'
                    from deputado""")
    for tabela in TABELAS_POR_LEGISLATURA:
        con.execute(f"delete from pg.publicado.{tabela} where legislatura = ?", p)

    con.execute(
        """insert into pg.publicado.mandato
           select v.id_camara, ?, arg_max(v.partido, v.data_hora), arg_max(v.uf, v.data_hora)
           from voto v join votacao_valida vv on vv.id = v.id_votacao and vv.legislatura = ?
           group by 1""",
        [legislatura, legislatura],
    )
    con.execute(
        f"""insert into pg.publicado.posicao
            select i.id_camara, i.legislatura, i.variante, 'voto', i.nota, i.nota_p05,
                   i.nota_p95, i.faixa, coalesce(e.faixa_exibida, i.faixa),
                   coalesce(e.fronteira, false), i.n_votos, '{METODOLOGIA_VERSAO}'
            from ideologia i
            left join ideologia_exibicao e using (id_camara, legislatura, variante)
            where i.legislatura = ? and list_contains(?, i.variante)
            union all
            select id_camara, legislatura, variante, 'campo', nota_campo, nota_campo_p05,
                   nota_campo_p95, faixa(nota_campo), faixa(nota_campo), false, n_votos,
                   '{METODOLOGIA_VERSAO}'
            from ideologia where legislatura = ? and list_contains(?, variante)""",
        [legislatura, variantes, legislatura, variantes],
    )
    con.execute(
        """insert into pg.publicado.posicao_partido
           select i.partido, i.legislatura, i.variante, count(*), median(i.nota),
                  faixa(median(i.nota)), any_value(e.nota)
           from ideologia i left join nota_especialistas e using (partido)
           where i.legislatura = ? and list_contains(?, i.variante) and i.partido is not null
           group by all having count(*) >= 3""",
        [legislatura, variantes],
    )
    con.execute(
        """insert into pg.publicado.governismo
           select id_camara, legislatura, governo, coalesce(ano::varchar, 'legislatura'),
                  n_total, taxa_total, n_disputadas, taxa_disputadas, suficiente
           from governismo where legislatura = ?""",
        p,
    )
    con.execute(
        """insert into pg.publicado.fidelidade
           select id_camara, legislatura, coalesce(ano::varchar, 'legislatura'), n, taxa,
                  suficiente
           from fidelidade where legislatura = ?""",
        p,
    )
    # Votações que mais empurraram o deputado para o lado em que está: discriminação da
    # votação × direção do voto, no sentido da posição dele em relação ao centro da Câmara.
    con.execute(
        f"""insert into pg.publicado.votacao_explicativa
            with centro as (
                select variante, median(theta) as c from ideologia
                where legislatura = ? group by 1
            ),
            contribuicao as (
                select i.id_camara, i.variante, vt.id_votacao, vt.voto_original,
                       iv.beta * (2 * vt.voto_codificado - 1) * sign(i.theta - c.c) as peso
                from ideologia i
                join centro c using (variante)
                join voto vt on vt.id_camara = i.id_camara and vt.voto_codificado is not null
                join ideologia_votacao iv on iv.id_votacao = vt.id_votacao
                     and iv.variante = i.variante and iv.legislatura = i.legislatura
                where i.legislatura = ? and list_contains(?, i.variante)
            ),
            uma_por_proposicao as (
                -- várias votações do mesmo projeto (urgência, texto, destaques): fica a de
                -- maior peso, para a lista mostrar projetos diferentes
                select c.* from contribuicao c
                left join votacao_proposicao_principal vp using (id_votacao)
                qualify row_number() over (
                    partition by c.id_camara, c.variante, coalesce(vp.id_proposicao, c.id_votacao)
                    order by c.peso desc, c.id_votacao) = 1
            ),
            ordenado as (
                select *, row_number() over (
                    partition by id_camara, variante order by peso desc, id_votacao) as ordem
                from uma_por_proposicao
            )
            select o.id_camara, ?, o.variante, o.ordem, o.id_votacao, v.data, v.descricao,
                   v.tipo, vp.sigla_tipo || ' ' || vp.numero || '/' || vp.ano, vp.ementa,
                   '{URL_PROPOSICAO}' || vp.id_proposicao,
                   o.voto_original, og.orientacao_original, o.peso,
                   '{URL_VOTACAO}' || o.id_votacao
            from ordenado o
            join votacao v on v.id = o.id_votacao
            left join votacao_proposicao_principal vp on vp.id_votacao = o.id_votacao
            left join orientacao og on og.id_votacao = o.id_votacao and og.bancada = 'Governo'
            where o.ordem <= {N_VOTACOES_EXPLICATIVAS}""",
        [legislatura, legislatura, variantes, legislatura],
    )
    con.execute(
        """insert into pg.publicado.validacao
           select legislatura, criterio, variante, valor, meta, status, detalhe, obrigatorio,
                  versao_metodologia, gerado_em
           from validacao where legislatura = ?""",
        p,
    )
    con.execute(
        """insert into pg.publicado.publicacao
           select (select coalesce(max(id), 0) + 1 from pg.publicado.publicacao), ?, ?, ?,
                  max(data), now()
           from votacao_valida where legislatura = ?""",
        [legislatura, METODOLOGIA_VERSAO, variantes, legislatura],
    )


def publicar(legislatura: int, base: Path = CAMINHO_BASE, url: str | None = None) -> list[str]:
    """Publica as variantes aprovadas da legislatura. Devolve as variantes publicadas."""
    # Sessão em memória: a base local entra só para leitura e o Postgres para escrita (abrir a
    # base local em modo somente leitura estenderia esse modo ao Postgres anexado).
    with duckdb.connect() as con:
        con.execute("attach ? as local (read_only)", [str(base)])
        con.execute("use local")
        variantes = variantes_publicaveis(con, legislatura)
        if not variantes:
            raise ErroPublicacao("nenhuma variante aprovada na validação; nada foi publicado")
        con.create_function("faixa", faixa, [float], str)
        con.execute("install postgres; load postgres;")
        con.execute("attach ? as pg (type postgres)", [url or url_banco()])
        for comando in _comandos(ESQUEMA_PG.read_text(encoding="utf-8")):
            con.execute("call postgres_execute('pg', ?)", [comando])
        con.execute("begin transaction")
        try:
            _carregar(con, legislatura, variantes)
            con.execute("commit")
        except Exception:
            con.execute("rollback")
            raise
    log.info("legislatura %d publicada (%s)", legislatura, ", ".join(variantes))
    return variantes
