"""Constrói a base municipal (DuckDB) a partir dos JSON do SAPL e, nas câmaras que migraram,
do Siscam. Sempre recria do zero."""

import json
import logging
import re
import unicodedata
from datetime import date
from pathlib import Path

import duckdb
import pyarrow as pa

from polaritics.base.partidos import harmonizar
from polaritics.coleta import especialistas
from polaritics.config import DIR_BRUTOS
from polaritics.municipal.config import CAMINHO_BASE_MUNICIPAL, Municipio
from polaritics.municipal.siscam import VOTANTE

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
    _executemany(
        con,
        "insert into prefeito values (?, ?, ?, ?, ?)",
        [
            (m.slug, p.nome, p.partido_na_posse, p.periodo.inicio, p.periodo.fim)
            for p in m.prefeitos
        ],
    )
    legislaturas = {r["id"]: r for r in _ler(brutos, "legislatura")}
    _executemany(
        con,
        "insert into legislatura values (?, ?, ?, ?)",
        [(m.slug, r["numero"], r["data_inicio"], r["data_fim"]) for r in legislaturas.values()],
    )
    _executemany(
        con,
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
    _executemany(
        con,
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
    _executemany(
        con,
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
        select ?::varchar as municipio, r.id::varchar as id_votacao,
               left(r.data_hora::varchar, 10)::date as data, r.materia::varchar as id_materia,
               r.numero_votos_sim as placar_sim, r.numero_votos_nao as placar_nao,
               t.natureza = 'A' as aprovada
        from {_json(brutos, "registrovotacao")} r
        left join {_json(brutos, "tiporesultado")} t on t.id = r.tipo_resultado_votacao
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
               '{m.sapl}/materia/' || r.id_materia, r.aprovada
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
    _executemany(
        con,
        "insert into sessao values (?, ?, ?, ?)",
        [
            (m.slug, str(r["id"]), r["data_inicio"], tipos.get(r["tipo"]))
            for r in _ler(brutos, "sessao")
            if r.get("finalizada")
        ],
    )
    _executemany(
        con,
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


def _executemany(con, sql: str, linhas) -> None:
    """`executemany` que aceita lista vazia (o DuckDB recusa)."""
    if linhas := list(linhas):
        con.executemany(sql, linhas)


def _inserir(con, tabela: str, linhas: list[dict], consulta: str = "select * from linhas") -> None:
    """Insere linhas (dicts) pela tabela Arrow; lista vazia não insere nada."""
    if linhas:
        con.register("linhas", pa.Table.from_pylist(linhas))
        con.execute(f"insert into {tabela} {consulta}")
        con.unregister("linhas")


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
    votacoes = [
        r
        for r in _ler(brutos, "siscam_votacoes")
        if r["tipo"] == "Nominal" and (corte is None or r["data"] > corte)
    ]
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
                "aprovada": (r.get("resultado") or "").lower().startswith("aprovad"),
            }
        )
    _inserir(con, "materia", list(materias.values()))
    _inserir(
        con,
        "votacao",
        linhas_votacao,
        """select v.municipio, v.id_votacao, v.data::date, l.numero, v.id_materia, v.placar_sim,
                  v.placar_nao, v.tipo, v.eh_mocao, v.url, v.aprovada
           from linhas v
           left join legislatura l on l.municipio = v.municipio
                and v.data::date between l.inicio and l.fim""",
    )
    _inserir(con, "voto", linhas_voto)

    # Presença: presente na sessão quem aparece em "Presentes" em alguma chamada dela
    sessoes = {}
    for r in frequencias:
        if r["id_sessao"] is None:
            continue
        tipo = re.search(r"Sessão (Ordinária|Extraordinária|Solene)", r["sessao"] or "")
        dia = min(r["data"], sessoes.get(r["id_sessao"], (r["data"],))[0])
        sessoes[r["id_sessao"]] = (dia, f"Sessão {tipo[1]}" if tipo else None)
    _executemany(
        con,
        "insert into sessao values (?, ?, ?, ?)",
        [(m.slug, PREFIXO_SISCAM + str(i), dia, tipo) for i, (dia, tipo) in sessoes.items()],
    )
    _executemany(
        con,
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


# Ementas de projetos que só dão nome a vias e próprios públicos (homenagens).
DENOMINACAO = re.compile(
    r"^\W*(denomina|d[aá] denomina[cç][aã]o|d[aá] nome|altera a denomina[cç][aã]o)", re.I
)
NUMERO_ANO = re.compile(r"N[ºo°]\s*(\d+)/(\d{4})")


def chave_materia(titulo: str) -> tuple[str | None, int | None, int | None]:
    """(tipo, número, ano) da matéria pelo título, para ligar documentos e votações."""
    sigla, _ = classificar_titulo(titulo)
    numero = NUMERO_ANO.search(titulo)
    return (sigla, int(numero[1]), int(numero[2])) if numero else (sigla, None, None)


def _carregar_projetos(con, m: Municipio, brutos: Path) -> None:
    """Projetos de 2021 em diante, do Siscam, inclusive o período do SAPL: a lista de projetos
    por ano bate com a do SAPL e só o Siscam continua atualizada (M9). Aprovado = alguma
    votação da própria matéria (nominal ou simbólica) com resultado de aprovação."""
    if not (brutos / "siscam_projetos.json").exists():
        return
    cadastro = {
        normalizar_nome(nome): id_
        for id_, nome in con.execute(
            "select id_vereador, nome from vereador where municipio = ?", [m.slug]
        ).fetchall()
    }
    executivo = {normalizar_nome(p.nome) for p in m.prefeitos} | {"poder executivo"}
    aprovados = {
        chave_materia(r["titulo"])
        for r in _ler(brutos, "siscam_votacoes")
        if (r.get("resultado") or "").lower().startswith("aprovad")
    }
    linhas = []
    for r in _ler(brutos, "siscam_projetos"):
        chave = chave_materia(r["titulo"])
        if chave[0] not in TIPOS_PROJETO | {"PR"}:
            continue
        autoria = r["autoria"] or ""
        autores = [cadastro.get(normalizar_nome(nome)) for _, nome in VOTANTE.findall(autoria)]
        linhas.append(
            {
                "municipio": m.slug,
                "id_projeto": str(r["id"]),
                "titulo": r["titulo"],
                "sigla_tipo": chave[0],
                "numero": chave[1],
                "ano": chave[2],
                "data": r["data"],
                "ementa": r["ementa"],
                "id_vereador": next((a for a in autores if a), None),
                "do_executivo": any(
                    normalizar_nome(a.strip()) in executivo for a in autoria.split(",")
                ),
                "denominacao": bool(DENOMINACAO.match(r["ementa"] or "")),
                "aprovado": chave in aprovados,
                "url": f"{m.siscam}/Siscam/Documentos/Details?id={r['id']}",
            }
        )
    _inserir(con, "projeto", linhas, "select * replace (data::date as data) from linhas")


CATEGORIAS_RECEITA = ("fundo_especial", "fundo_partidario", "proprios", "pessoas_fisicas", "outros")
PIV = re.compile(r"PIV\s*(?:N[ºo°.]*\s*)?(\d+)\s*/\s*(\d{4})", re.I)


# Na ementa do PIV, a lista de vereadores vem antes da dos acompanhantes; corta-se a partir da
# primeira menção a servidor para que o nome de um assessor não seja lido como de vereador.
ACOMPANHANTES = re.compile(
    r"\b(assessor|assessora|assessores|servidor|servidora|servidores|serv\.|motorista|"
    r"advogad|analista|oficial legislativo|diretor|diretora|chefe de|contador|procurador)",
    re.I,
)
VEREADOR_NO_EMPENHO = re.compile(r"\bVER(?:EADOR|EADORA)?\.?\s+([A-ZÀ-Ü][A-ZÀ-Ü ]+)")


def apelidos(vereadores: dict[str, tuple[str, str | None]]) -> dict[str, str]:
    """Apelido → vereador, com o nome parlamentar inteiro e cada palavra dele (4+ letras) que
    aponte para um único vereador da legislatura. Palavras compartilhadas ("Garcia", "Farmácia")
    ficam de fora."""
    candidatos: dict[str, set[str]] = {}
    for id_, (nome, _) in vereadores.items():
        normal = normalizar_nome(nome)
        candidatos.setdefault(normal, set()).add(id_)
        for palavra in re.findall(r"[a-z]{4,}", normal):
            candidatos.setdefault(palavra, set()).add(id_)
    return {apelido: next(iter(ids)) for apelido, ids in candidatos.items() if len(ids) == 1}


def participantes(
    autoria: str, ementa: str, historicos: list[str], vereadores: dict[str, tuple[str, str | None]]
) -> set[str]:
    """Vereadores de uma viagem, por três sinais: a autoria completa do PIV ("Nome civil (Nome
    parlamentar)"), os apelidos na ementa antes da lista de acompanhantes e o nome civil depois
    de "VER." no histórico dos empenhos (metodologia municipal, M10)."""
    por_parlamentar = {normalizar_nome(n): id_ for id_, (n, _) in vereadores.items()}
    por_civil = {normalizar_nome(c): id_ for id_, (_, c) in vereadores.items() if c}
    achados = {
        por_parlamentar[normalizar_nome(nome)]
        for _, nome in VOTANTE.findall(autoria or "")
        if normalizar_nome(nome) in por_parlamentar
    }
    trecho = ACOMPANHANTES.split(ementa or "", maxsplit=1)[0]
    palavras = normalizar_nome(trecho)
    for apelido, id_ in apelidos(vereadores).items():
        if re.search(rf"\b{re.escape(apelido)}\b", palavras):
            achados.add(id_)
    for historico in historicos:
        for nome in VEREADOR_NO_EMPENHO.findall(historico or ""):
            nome = normalizar_nome(nome)
            achados |= {id_ for civil, id_ in por_civil.items() if nome.startswith(civil)}
    return achados


def _carregar_viagens(con, m: Municipio, brutos: Path) -> None:
    if not (brutos / "siscam_piv.json").exists():
        return
    empenhos = (
        _ler(brutos, "eddydata_viagens") if (brutos / "eddydata_viagens.json").exists() else []
    )
    # a anulação (EOA) tem o mesmo número do empenho (EMO) que anula, no mesmo exercício
    piv_do_empenho, historicos = {}, {}
    for r in empenhos:
        if r["especie"] == "EMO" and (achado := PIV.search(r["historico"] or "")):
            piv = (int(achado[1]), int(achado[2]))
            piv_do_empenho[(r["data"][:4], r["numero"])] = piv
            historicos.setdefault(piv, []).append(r["historico"])
    mandatos = con.execute(
        """select m.id_vereador, v.nome, v.nome_completo, m.inicio, m.fim
           from mandato m join vereador v using (municipio, id_vereador)
           where m.municipio = ?""",
        [m.slug],
    ).fetchall()
    viagens, presentes = {}, set()
    for r in _ler(brutos, "siscam_piv"):
        numero = NUMERO_ANO.search(r["titulo"])
        if not numero or not r["data"]:
            continue
        chave = (int(numero[1]), int(numero[2]))
        viagens[chave] = (
            m.slug,
            *chave,
            r["data"],
            r["ementa"],
            f"{m.siscam}/Siscam/Documentos/Details?id={r['id']}",
        )
        dia = date.fromisoformat(r["data"])
        em_exercicio = {
            id_: (nome, civil) for id_, nome, civil, ini, fim in mandatos if ini <= dia <= fim
        }
        for id_ in participantes(
            r["autoria"], r["ementa"], historicos.get(chave, []), em_exercicio
        ):
            presentes.add((m.slug, *chave, id_))
    _executemany(con, "insert into viagem values (?, ?, ?, ?, ?, ?)", list(viagens.values()))
    _executemany(con, "insert into viagem_vereador values (?, ?, ?, ?)", sorted(presentes))
    _executemany(
        con,
        "insert into despesa_viagem values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                m.slug,
                str(r["id"]),
                r["numero"],
                r["data"],
                r["especie"],
                r["valor"],
                r["despesa"],
                *piv_do_empenho.get((r["data"][:4], r["numero"]), (None, None)),
            )
            for r in empenhos
        ],
    )


def _carregar_folha(con, m: Municipio, brutos: Path) -> None:
    if not (brutos / "eddydata_folha.json").exists():
        return
    _executemany(
        con,
        "insert into folha values (?, ?, ?, ?, ?, ?, ?)",
        [
            (m.slug, r["ano"], r["mes"], r["nome"], r["cargo"], r["calculo"], r["valor_bruto"])
            for r in _ler(brutos, "eddydata_folha")
        ],
    )


def _valor_tse(texto: str) -> float:
    return float((texto or "0").replace(".", "").replace(",", ".")) if texto != "#NULO" else 0.0


def categoria_receita(origem: str, fonte: str) -> str:
    """Origem do dinheiro de campanha: fundos públicos pela fonte; o resto pela origem."""
    if fonte == "FUNDO ESPECIAL":
        return "fundo_especial"
    if fonte == "FUNDO PARTIDARIO":
        return "fundo_partidario"
    if origem == "Recursos próprios":
        return "proprios"
    if origem in ("Recursos de pessoas físicas", "Recursos de Financiamento Coletivo"):
        return "pessoas_fisicas"
    return "outros"


def _carregar_campanha(con, m: Municipio, brutos: Path) -> None:
    """Liga o candidato ao vereador pelo nome civil e, se não achar, pelo nome de urna."""
    cadastro = con.execute(
        "select id_vereador, nome, nome_completo from vereador where municipio = ?", [m.slug]
    ).fetchall()
    por_civil = {normalizar_nome(c): id_ for id_, _, c in cadastro if c}
    por_urna = {normalizar_nome(n): id_ for id_, n, _ in cadastro}
    for arquivo in sorted(brutos.glob("tse_candidatos_*.json")):
        ano = int(arquivo.stem.rsplit("_", 1)[1])
        ids = {}
        for c in _ler(brutos, arquivo.stem):
            id_ = por_civil.get(normalizar_nome(c["NM_CANDIDATO"])) or por_urna.get(
                normalizar_nome(c["NM_URNA_CANDIDATO"])
            )
            if id_:
                ids[c["SQ_CANDIDATO"]] = (id_, c["SG_PARTIDO"], c["DS_SIT_TOT_TURNO"])
        totais = {sq: dict.fromkeys(CATEGORIAS_RECEITA, 0.0) | {"despesa": 0.0} for sq in ids}
        for r in _ler(brutos, f"tse_receitas_{ano}"):
            if r["SQ_CANDIDATO"] in totais:
                categoria = categoria_receita(r["DS_ORIGEM_RECEITA"], r["DS_FONTE_RECEITA"])
                totais[r["SQ_CANDIDATO"]][categoria] += _valor_tse(r["VR_RECEITA"])
        for r in _ler(brutos, f"tse_despesas_{ano}"):
            if r["SQ_CANDIDATO"] in totais:
                totais[r["SQ_CANDIDATO"]]["despesa"] += _valor_tse(r["VR_DESPESA_CONTRATADA"])
        _executemany(
            con,
            "insert into campanha values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    m.slug,
                    id_,
                    ano,
                    partido,
                    situacao,
                    sum(totais[sq][c] for c in CATEGORIAS_RECEITA),
                    *(totais[sq][c] for c in CATEGORIAS_RECEITA),
                    totais[sq]["despesa"],
                )
                for sq, (id_, partido, situacao) in ids.items()
            ],
        )


def _carregar_especialistas(con, arquivo: Path) -> None:
    if not arquivo.exists():
        log.warning("notas dos especialistas ausentes (%s); rode `municipal coletar`", arquivo)
        return
    _executemany(
        con,
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
                _carregar_projetos(con, m, brutos)
                _carregar_viagens(con, m, brutos)
            _carregar_folha(con, m, brutos)
            _carregar_campanha(con, m, brutos)
    temporario.replace(destino)
    log.info("base municipal construída em %s", destino)
    return destino
