"""Constrói a base municipal (DuckDB) a partir dos JSON do SAPL e, nas câmaras que migraram,
do Siscam. Sempre recria do zero."""

import json
import logging
import re
import unicodedata
from pathlib import Path

import duckdb
import pyarrow as pa

from polaritics.base.partidos import harmonizar
from polaritics.coleta import especialistas
from polaritics.config import DIR_BRUTOS
from polaritics.municipal.config import CAMINHO_BASE_MUNICIPAL, Municipio

log = logging.getLogger(__name__)

ESQUEMA = Path(__file__).with_name("esquema.sql")

# Siglas usadas pelo SAPL (inclusive de partidos já extintos) → sigla dos especialistas.
SIGLAS_SAPL = {
    "REP": "REPUBLICANOS",
    "PRB": "REPUBLICANOS",
    "CID": "CIDADANIA",
    "PPS": "CIDADANIA",
    "SD": "SOLIDARIEDADE",
    "PMDB": "MDB",
    "PR": "PL",
    "DEM": "UNIÃO",  # fusão de DEM e PSL (TSE, 08/02/2022)
    "PSL": "UNIÃO",
    "PSDC": "DC",
    "PTdoB": "AVANTE",
    "PEN": "PATRIOTA",
    "PHS": "PODE",  # incorporado ao Podemos (2019)
    "PRP": "PATRIOTA",  # incorporado ao Patriota (2019)
    "PPL": "PCdoB",  # incorporado ao PCdoB (2019)
}

# Tipos de matéria cuja votação é de procedimento (metodologia municipal, M3).
TIPOS_PROCEDIMENTO = {"Req", "RU", "ATA", "RF"}
# Tipos de matéria em que o voto Sim acompanha o autor (governismo, M5).
TIPOS_PROJETO = {"PLO", "PLC", "PELOM", "PDL"}


def sigla_partido(sigla_sapl: str) -> str:
    sigla = harmonizar(sigla_sapl) or sigla_sapl
    return SIGLAS_SAPL.get(sigla, sigla)


def url_publica(url: str | None, municipio: Municipio) -> str | None:
    """O SAPL devolve links com o host interno (ex.: sapl.dmz...); troca pelo endereço público."""
    if not url:
        return None
    return re.sub(r"^https?://[^/]+", municipio.sapl, url)


def _ler(brutos: Path, nome: str) -> list[dict]:
    return json.loads((brutos / f"{nome}.json").read_text(encoding="utf-8"))


def _json(brutos: Path, nome: str) -> str:
    """Leitura direta pelo DuckDB, para os arquivos grandes (votos, matérias)."""
    return f"read_json_auto('{brutos / f'{nome}.json'}', maximum_object_size=1000000000)"


def _carregar_municipio(con, m: Municipio, brutos: Path) -> None:
    con.execute("insert into municipio values (?, ?, ?, ?)", [m.slug, m.nome, m.uf, m.sapl])
    con.executemany(
        "insert into prefeito values (?, ?, ?, ?, ?)",
        [
            (m.slug, p.nome, p.partido_na_posse, p.periodo.inicio, p.periodo.fim)
            for p in m.prefeitos
        ],
    )
    legislaturas = {r["id"]: r for r in _ler(brutos, "legislatura")}
    con.executemany(
        "insert into legislatura values (?, ?, ?, ?)",
        [(m.slug, r["numero"], r["data_inicio"], r["data_fim"]) for r in legislaturas.values()],
    )
    con.executemany(
        "insert into vereador values (?, ?, ?, ?, ?, ?)",
        [
            (
                m.slug,
                str(r["id"]),
                r["nome_parlamentar"],
                r.get("nome_completo") or None,
                r.get("sexo") or None,
                url_publica(r.get("fotografia"), m),
            )
            for r in _ler(brutos, "parlamentar")
        ],
    )
    con.executemany(
        "insert into mandato values (?, ?, ?, ?, ?, ?)",
        [
            (
                m.slug,
                str(r["parlamentar"]),
                legislaturas[r["legislatura"]]["numero"],
                r["data_inicio_mandato"],
                r["data_fim_mandato"],
                r.get("titular"),
            )
            for r in _ler(brutos, "mandato")
        ],
    )
    partidos = {r["id"]: r["sigla"] for r in _ler(brutos, "partido")}
    con.executemany(
        "insert into filiacao values (?, ?, ?, ?, ?, ?)",
        [
            (
                m.slug,
                str(r["parlamentar"]),
                partidos[r["partido"]],
                sigla_partido(partidos[r["partido"]]),
                r["data"],
                r.get("data_desfiliacao"),
            )
            for r in _ler(brutos, "filiacao")
        ],
    )


def _carregar_materias(con, m: Municipio, brutos: Path) -> None:
    tipos_autor = {r["id"]: r.get("descricao") or r["__str__"] for r in _ler(brutos, "tipoautor")}
    executivo = {
        r["id"]
        for r in _ler(brutos, "autor")
        if "executivo" in tipos_autor.get(r["tipo"], "").lower()
    }
    if not executivo:
        raise ValueError(f"{m.slug}: nenhum autor do tipo chefe do Executivo no SAPL")
    con.execute(
        f"""
        insert into materia
        select ?, m.id::varchar, t.descricao || ' nº ' || m.numero || ' de ' || m.ano, t.sigla,
               t.descricao, m.numero, m.ano,
               nullif(trim(m.ementa), ''), list_has_any(m.autores, ?::bigint[])
        from {_json(brutos, "materia")} m
        left join {_json(brutos, "tipomateria")} t on t.id = m.tipo
        """,
        [m.slug, sorted(executivo)],
    )


def _carregar_votacoes(con, m: Municipio, brutos: Path) -> None:
    # data local da votação, como registrada (o horário vem com o fuso de Brasília)
    con.execute(
        f"""
        create temp table registro as
        select ?::varchar as municipio, id::varchar as id_votacao,
               left(data_hora::varchar, 10)::date as data, materia::varchar as id_materia,
               numero_votos_sim as placar_sim, numero_votos_nao as placar_nao
        from {_json(brutos, "registrovotacao")}
        """,
        [m.slug],
    )
    procedimento = ", ".join(f"'{t}'" for t in TIPOS_PROCEDIMENTO)
    con.execute(f"""
        insert into votacao
        select r.municipio, r.id_votacao, r.data, l.numero, r.id_materia, r.placar_sim,
               r.placar_nao,
               case when mt.sigla_tipo in ({procedimento}) then 'procedimento' else 'merito' end,
               coalesce(lower(mt.tipo) like 'moção%', false),
               '{m.sapl}/materia/' || r.id_materia
        from registro r
        left join materia mt on mt.municipio = r.municipio and mt.id_materia = r.id_materia
        left join legislatura l on l.municipio = r.municipio and r.data between l.inicio and l.fim
    """)
    # um voto por vereador e votação; se o SAPL tiver registro repetido, vale o mais recente
    con.execute(
        f"""
        insert into voto
        select ?, votacao::varchar, parlamentar::varchar, voto,
               case voto when 'Sim' then 1 when 'Não' then 0 end
        from {_json(brutos, "votoparlamentar")}
        qualify row_number() over (partition by votacao, parlamentar order by id desc) = 1
        """,
        [m.slug],
    )


def _carregar_presenca(con, m: Municipio, brutos: Path) -> None:
    tipos = {r["id"]: r["nome"] for r in _ler(brutos, "tiposessao")}
    con.executemany(
        "insert into sessao values (?, ?, ?, ?)",
        [
            (m.slug, str(r["id"]), r["data_inicio"], tipos.get(r["tipo"]))
            for r in _ler(brutos, "sessao")
            if r.get("finalizada")
        ],
    )
    con.executemany(
        "insert into presenca values (?, ?, ?)",
        [
            (m.slug, str(r["sessao_plenaria"]), str(r["parlamentar"]))
            for r in _ler(brutos, "presenca")
        ],
    )


# Início do título da matéria no Siscam (sem a sigla "XX - ") → (sigla, tipo), nas siglas do
# SAPL usadas pelas regras de procedimento e de governismo. A ordem importa: o mais específico
# primeiro.
TIPOS_SISCAM = [
    ("requerimento urgência", ("RU", "Requerimento de Urgência")),
    ("requerimento de urgência", ("RU", "Requerimento de Urgência")),
    ("requerimento", ("Req", "Requerimento")),
    ("ata", ("ATA", "Ata")),
    ("redação final", ("RF", "Redação final")),
    ("moção", ("MO", "Moção")),
    ("projeto de lei complementar", ("PLC", "Projeto de Lei Complementar")),
    ("projeto de lei", ("PLO", "Projeto de Lei Ordinária")),
    ("projeto de emenda à lei orgânica", ("PELOM", "Projeto de Emenda à Lei Orgânica")),
    ("projeto de decreto legislativo", ("PDL", "Projeto de Decreto Legislativo")),
    ("projeto de resolução", ("PR", "Projeto de Resolução")),
    ("emenda", ("Emen", "Emenda")),
    ("substitutivo", ("SUB", "Substitutivo")),
    ("veto", ("Veto", "Veto")),
    ("parecer", ("Par", "Parecer")),
    ("indicação", ("Ind", "Indicação")),
]
# Grupos de voto do Siscam → (voto como no SAPL, codificação da metodologia)
VOTOS_SISCAM = {
    "A Favor": ("Sim", 1),
    "Contra": ("Não", 0),
    "Abstenções": ("Abstenção", None),
    "Abstenção": ("Abstenção", None),
    "Não votaram": ("Não Votou", None),
    "Ausentes": ("Ausente", None),
}


def classificar_titulo(titulo: str) -> tuple[str | None, str | None]:
    """Tipo da matéria pelo título do Siscam (ex.: "PLO - Projeto de Lei Ordinária Nº 1/2026",
    "Emenda ao Projeto Nº 265/2021", "Moção ao Aplauso Nº 3/2025")."""
    texto = re.sub(r"^[A-Z]{1,6}\s*-\s*", "", titulo.strip()).lower()
    texto = re.sub(r"^em-", "", texto)
    for inicio, tipo in TIPOS_SISCAM:
        if texto.startswith(inicio):
            return tipo
    return None, None


def normalizar_nome(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


def _ids_por_nome(con, m: Municipio, nomes: set[str]) -> dict[str, str]:
    """Liga o nome parlamentar do Siscam ao vereador do cadastro do SAPL."""
    cadastro = {
        normalizar_nome(nome): id_
        for id_, nome in con.execute(
            "select id_vereador, nome from vereador where municipio = ?", [m.slug]
        ).fetchall()
    }
    faltando = sorted(n for n in nomes if normalizar_nome(n) not in cadastro)
    if faltando:
        raise ValueError(f"{m.slug}: vereadores do Siscam ausentes do cadastro: {faltando}")
    return {n: cadastro[normalizar_nome(n)] for n in nomes}


PREFIXO_SISCAM = "siscam-"  # ids do Siscam colidem com os do SAPL


def _carregar_siscam(con, m: Municipio, brutos: Path) -> None:
    """Votações, matérias e presença do Siscam posteriores à última votação do SAPL
    (metodologia municipal, M1). O histórico anterior que o Siscam herdou do SAPL tem votações
    ligadas a sessões e datas erradas, então o período do SAPL vem do próprio SAPL."""
    corte = con.execute(
        "select max(data)::varchar from votacao where municipio = ?", [m.slug]
    ).fetchone()[0]
    votacoes = [r for r in _ler(brutos, "siscam_votacoes") if corte is None or r["data"] > corte]
    frequencias = [
        r for r in _ler(brutos, "siscam_frequencias") if corte is None or r["data"] > corte
    ]
    log.info("%s: Siscam a partir de %s (%d votações)", m.slug, corte, len(votacoes))
    nomes = {v["nome"] for r in votacoes + frequencias for g in r["grupos"].values() for v in g}
    ids = _ids_por_nome(con, m, nomes)
    executivo = {p.nome for p in m.prefeitos} | {"Poder Executivo"}

    materias: dict[str, dict] = {}
    linhas_votacao, linhas_voto = [], []
    vistas = set()
    for r in sorted(votacoes, key=lambda r: r["id"]):
        # O Siscam repete algumas votações sob outro id (mesmo documento, sessão, dia e votos).
        # Como na Câmara (metodologia, seção 3), fica só o primeiro registro.
        chave = (r["titulo"], r["id_sessao"], r["data"], json.dumps(r["grupos"], sort_keys=True))
        if r["grupos"] and chave in vistas:
            continue
        vistas.add(chave)
        sigla, tipo = classificar_titulo(r["titulo"])
        autores = {a.strip() for a in (r["autoria"] or "").split(",")}
        numero = re.search(r"N[ºo°]\s*(\d+)/(\d{4})", r["titulo"])
        mat = materias.setdefault(
            r["titulo"],
            {
                "municipio": m.slug,
                "id_materia": r["titulo"],
                "titulo": r["titulo"],
                "sigla_tipo": sigla,
                "tipo": tipo,
                "numero": int(numero[1]) if numero else None,
                "ano": int(numero[2]) if numero else None,
                "ementa": r["ementa"],
                "do_executivo": False,
            },
        )
        mat["do_executivo"] = mat["do_executivo"] or bool(autores & executivo)
        desconhecidos = set(r["grupos"]) - set(VOTOS_SISCAM)
        if desconhecidos:
            raise ValueError(f"votação {r['id']}: grupos de voto desconhecidos {desconhecidos}")
        for grupo, votantes in r["grupos"].items():
            original, codificado = VOTOS_SISCAM[grupo]
            for v in votantes:
                linhas_voto.append(
                    {
                        "municipio": m.slug,
                        "id_votacao": PREFIXO_SISCAM + str(r["id"]),
                        "id_vereador": ids[v["nome"]],
                        "voto_original": original,
                        "voto_codificado": codificado,
                    }
                )
        linhas_votacao.append(
            {
                "municipio": m.slug,
                "id_votacao": PREFIXO_SISCAM + str(r["id"]),
                "data": r["data"],
                "id_materia": r["titulo"],
                "placar_sim": len(r["grupos"].get("A Favor", [])),
                "placar_nao": len(r["grupos"].get("Contra", [])),
                "tipo": "procedimento" if sigla in TIPOS_PROCEDIMENTO else "merito",
                "eh_mocao": sigla == "MO",
                "url": f"{m.siscam}/Siscam/Votacoes/Details?id={r['id']}",
            }
        )
    con.register("materias_siscam", pa.Table.from_pylist(list(materias.values())))
    con.execute("insert into materia select * from materias_siscam")
    con.register("votacoes_siscam", pa.Table.from_pylist(linhas_votacao))
    con.execute("""
        insert into votacao
        select v.municipio, v.id_votacao, v.data::date, l.numero, v.id_materia, v.placar_sim,
               v.placar_nao, v.tipo, v.eh_mocao, v.url
        from votacoes_siscam v
        left join legislatura l on l.municipio = v.municipio
             and v.data::date between l.inicio and l.fim
    """)
    con.register("votos_siscam", pa.Table.from_pylist(linhas_voto))
    con.execute("insert into voto select * from votos_siscam")

    # Presença: presente na sessão quem aparece em "Presentes" em alguma chamada dela
    sessoes = {}
    for r in frequencias:
        if r["id_sessao"] is None:
            continue
        tipo = re.search(r"Sessão (Ordinária|Extraordinária|Solene)", r["sessao"] or "")
        dia = min(r["data"], sessoes.get(r["id_sessao"], (r["data"],))[0])
        sessoes[r["id_sessao"]] = (dia, f"Sessão {tipo[1]}" if tipo else None)
    con.executemany(
        "insert into sessao values (?, ?, ?, ?)",
        [(m.slug, PREFIXO_SISCAM + str(i), dia, tipo) for i, (dia, tipo) in sessoes.items()],
    )
    con.executemany(
        "insert into presenca values (?, ?, ?)",
        sorted(
            {
                (m.slug, PREFIXO_SISCAM + str(r["id_sessao"]), ids[v["nome"]])
                for r in frequencias
                if r["id_sessao"] is not None
                for v in r["grupos"].get("Presentes", [])
            }
        ),
    )


def _carregar_especialistas(con, arquivo: Path) -> None:
    if not arquivo.exists():
        log.warning("notas dos especialistas ausentes (%s); rode `municipal coletar`", arquivo)
        return
    con.executemany(
        "insert into nota_especialistas values (?, ?, ?)",
        [(n.partido, n.nota, n.origem) for n in especialistas.notas_2022(arquivo)],
    )


def divergencias_placar(con, municipio: str) -> list[tuple]:
    """Registros em que o placar oficial não bate com a soma dos votos individuais."""
    return con.execute(
        """select v.id_votacao, v.data, v.placar_sim, v.placar_nao,
                  count(*) filter (vt.voto_codificado = 1), count(*) filter (vt.voto_codificado = 0)
           from votacao v join voto vt using (municipio, id_votacao)
           where v.municipio = ?
           group by all
           having v.placar_sim <> count(*) filter (vt.voto_codificado = 1)
               or v.placar_nao <> count(*) filter (vt.voto_codificado = 0)
           order by v.data""",
        [municipio],
    ).fetchall()


def construir_base(
    municipios: list[Municipio],
    destino: Path = CAMINHO_BASE_MUNICIPAL,
    arquivo_especialistas: Path = especialistas.ARQUIVO,
    raiz_brutos: Path = DIR_BRUTOS / "municipal",
) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(".duckdb.construindo")
    temporario.unlink(missing_ok=True)
    with duckdb.connect(str(temporario)) as con:
        con.execute(ESQUEMA.read_text(encoding="utf-8"))
        _carregar_especialistas(con, arquivo_especialistas)
        for m in municipios:
            brutos = raiz_brutos / m.slug
            _carregar_municipio(con, m, brutos)
            _carregar_materias(con, m, brutos)
            _carregar_votacoes(con, m, brutos)
            _carregar_presenca(con, m, brutos)
            if m.siscam:
                _carregar_siscam(con, m, brutos)
    temporario.replace(destino)
    log.info("base municipal construída em %s", destino)
    return destino
