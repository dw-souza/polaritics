import json
from datetime import date

import duckdb
import httpx
import numpy as np
import pytest

from polaritics.config import Periodo
from polaritics.municipal import base as base_mun
from polaritics.municipal import siscam
from polaritics.municipal.coleta import ColetorSAPL, ErroColetaSAPL
from polaritics.municipal.config import Municipio, Prefeito
from polaritics.municipal.ideologia import (
    ReguaGrupos,
    grupos_de_votacao,
    partido_na_legislatura,
    posicoes_na_camara,
)
from polaritics.municipal.medidas import calcular_governismo, calcular_presenca

MUNICIPIO = Municipio(
    "teste",
    "Teste",
    "SP",
    "https://sapl.teste.sp.leg.br",
    (Prefeito("Prefeita", "MDB", Periodo(date(2025, 1, 1), date(2028, 12, 31))),),
)

TIPOS = [
    {"id": 2, "sigla": "PLO", "descricao": "Projeto de Lei Ordinária"},
    {"id": 17, "sigla": "RU", "descricao": "Requerimento de Urgência"},
    {"id": 14, "sigla": "MOA", "descricao": "Moção de Apoio"},
    {"id": 11, "sigla": "Emen", "descricao": "Emenda"},
]


def _escrever(pasta, nome, registros):
    (pasta / f"{nome}.json").write_text(json.dumps(registros, ensure_ascii=False))


def registro(id_, materia, data="2025-03-10", sim=2, nao=1):
    return {
        "id": id_,
        "materia": materia,
        "data_hora": f"{data}T14:00:00-03:00",
        "numero_votos_sim": sim,
        "numero_votos_nao": nao,
    }


def voto(id_, votacao, parlamentar, valor):
    return {"id": id_, "votacao": votacao, "parlamentar": parlamentar, "voto": valor}


@pytest.fixture
def brutos(tmp_path):
    pasta = tmp_path / "raw" / "teste"
    pasta.mkdir(parents=True)
    _escrever(pasta, "legislatura", [
        {"id": 1, "numero": 11, "data_inicio": "2021-01-01", "data_fim": "2024-12-31"},
        {"id": 2, "numero": 12, "data_inicio": "2025-01-01", "data_fim": "2028-12-31"},
    ])  # fmt: skip
    _escrever(pasta, "parlamentar", [
        {"id": i, "nome_parlamentar": n, "nome_completo": None, "sexo": "F",
         "fotografia": f"http://sapl.dmz.teste.sp.leg.br/media/{i}.jpg" if i == 1 else None}
        for i, n in [(1, "Ana"), (2, "Bia"), (3, "Cris")]
    ])  # fmt: skip
    _escrever(pasta, "mandato", [
        {"parlamentar": i, "legislatura": 2, "data_inicio_mandato": "2025-01-01",
         "data_fim_mandato": "2028-12-31", "titular": True}
        for i in (1, 2, 3)
    ])  # fmt: skip
    _escrever(pasta, "partido", [
        {"id": 4, "sigla": "PT"}, {"id": 38, "sigla": "REP"}, {"id": 39, "sigla": "PL"},
    ])  # fmt: skip
    _escrever(pasta, "filiacao", [
        {"parlamentar": 1, "partido": 4, "data": "2000-01-01", "data_desfiliacao": None},
        # Bia troca de partido no meio da legislatura
        {"parlamentar": 2, "partido": 38, "data": "2020-01-01", "data_desfiliacao": "2025-04-01"},
        {"parlamentar": 2, "partido": 39, "data": "2025-04-02", "data_desfiliacao": None},
        {"parlamentar": 3, "partido": 39, "data": "2020-01-01", "data_desfiliacao": None},
    ])  # fmt: skip
    _escrever(pasta, "tipoautor", [
        {"id": 2, "descricao": "Parlamentar"},
        {"id": 7, "descricao": "Chefe do Poder Executivo Municipal"},
    ])  # fmt: skip
    _escrever(pasta, "autor", [{"id": 1, "tipo": 2}, {"id": 49, "tipo": 7}])
    _escrever(pasta, "tipomateria", TIPOS)
    _escrever(pasta, "materia", [
        {"id": 10, "tipo": 2, "numero": 1, "ano": 2025, "ementa": " Do prefeito ", "autores": [49]},
        {"id": 11, "tipo": 17, "numero": 2, "ano": 2025, "ementa": "Urgência", "autores": [1]},
        {"id": 12, "tipo": 14, "numero": 3, "ano": 2025, "ementa": "Apoio", "autores": [1]},
        {"id": 13, "tipo": 11, "numero": 4, "ano": 2025, "ementa": "", "autores": [49, 1]},
    ])  # fmt: skip
    _escrever(pasta, "registrovotacao", [
        registro(100, 10),
        registro(101, 11, sim=3, nao=0),
        registro(102, 12, data="2025-05-10"),
        registro(103, 13, sim=1, nao=2),  # placar diferente dos votos (2 × 1)
    ])  # fmt: skip
    _escrever(pasta, "votoparlamentar", [
        voto(1, 100, 1, "Não"), voto(2, 100, 2, "Sim"), voto(3, 100, 3, "Sim"),
        voto(4, 101, 1, "Sim"), voto(5, 101, 2, "Sim"), voto(6, 101, 3, "Sim"),
        voto(7, 102, 1, "Não"), voto(8, 102, 2, "Sim"), voto(9, 102, 3, "Sim"),
        voto(10, 103, 1, "Não"), voto(11, 103, 2, "Sim"), voto(12, 103, 3, "Não Votou"),
        voto(13, 103, 3, "Sim"),  # registro repetido: vale o de id maior
    ])  # fmt: skip
    _escrever(pasta, "tiposessao", [
        {"id": 3, "nome": "Sessão Ordinária"}, {"id": 2, "nome": "Sessão Solene"},
    ])  # fmt: skip
    _escrever(pasta, "sessao", [
        {"id": 1, "data_inicio": "2025-02-01", "tipo": 3, "finalizada": True},
        {"id": 2, "data_inicio": "2025-02-08", "tipo": 3, "finalizada": True},
        {"id": 3, "data_inicio": "2025-02-15", "tipo": 3, "finalizada": True},  # sem lista
        {"id": 4, "data_inicio": "2025-02-20", "tipo": 2, "finalizada": True},  # solene
    ])  # fmt: skip
    _escrever(pasta, "presenca", [
        {"sessao_plenaria": 1, "parlamentar": 1}, {"sessao_plenaria": 1, "parlamentar": 2},
        {"sessao_plenaria": 2, "parlamentar": 1}, {"sessao_plenaria": 4, "parlamentar": 3},
    ])  # fmt: skip
    especialistas = tmp_path / "experts.csv"
    especialistas.write_text("ideol_22_pt;ideol_22_pl;ideol_22_rep\n2;9;8\n3;8,6;8,6\n")
    return tmp_path, especialistas


@pytest.fixture
def con(brutos):
    raiz, especialistas = brutos
    destino = raiz / "municipal.duckdb"
    base_mun.construir_base([MUNICIPIO], destino, especialistas, raiz_brutos=raiz / "raw")
    with duckdb.connect(str(destino)) as conexao:
        yield conexao


def test_siglas_do_sapl_viram_as_dos_especialistas():
    assert base_mun.sigla_partido("REP") == "REPUBLICANOS"
    assert base_mun.sigla_partido("CID") == "CIDADANIA"
    assert base_mun.sigla_partido("DEM") == "UNIÃO"
    assert base_mun.sigla_partido("PT") == "PT"


def test_url_interna_do_sapl_vira_publica():
    url = base_mun.url_publica("http://sapl.dmz.teste.sp.leg.br/media/1.jpg", MUNICIPIO)
    assert url == "https://sapl.teste.sp.leg.br/media/1.jpg"
    assert base_mun.url_publica(None, MUNICIPIO) is None


def test_materias_do_executivo_e_tipos_de_votacao(con):
    executivo = con.execute(
        "select id_materia, do_executivo, ementa from materia order by 1"
    ).fetchall()
    assert executivo == [
        ("10", True, "Do prefeito"),
        ("11", False, "Urgência"),
        ("12", False, "Apoio"),
        ("13", True, None),
    ]
    votacoes = con.execute(
        "select id_votacao, legislatura, tipo, eh_mocao from votacao order by 1"
    ).fetchall()
    assert votacoes == [
        ("100", 12, "merito", False),
        ("101", 12, "procedimento", False),
        ("102", 12, "merito", True),
        ("103", 12, "merito", False),
    ]


def test_voto_repetido_fica_o_mais_recente_e_placar_e_conferido(con):
    assert con.execute(
        "select voto_original, voto_codificado from voto where id_votacao = '103' "
        "and id_vereador = '3'"
    ).fetchall() == [("Sim", 1)]
    divergentes = base_mun.divergencias_placar(con, "teste")
    assert [d[0] for d in divergentes] == ["103"]


def test_partido_na_legislatura_e_o_do_ultimo_voto(con):
    partidos = partido_na_legislatura(con, "teste", 12)
    assert partidos == {"1": "PT", "2": "PL", "3": "PL"}


def test_governismo_conta_so_projetos_do_executivo(con):
    calcular_governismo(con)
    linhas = con.execute(
        """select id_vereador, n_total, n_disputadas, taxa_disputadas, suficiente
           from governismo order by 1"""
    ).fetchall()
    # a emenda 13 é do Executivo, mas emendas não entram (M5)
    assert linhas == [
        ("1", 1, 1, 0.0, False),
        ("2", 1, 1, 1.0, False),
        ("3", 1, 1, 1.0, False),
    ]


def test_presenca_ignora_sessoes_sem_lista_e_solenes(con):
    calcular_presenca(con)
    linhas = con.execute(
        "select id_vereador, sessoes, presentes from presenca_plenario order by 1"
    ).fetchall()
    assert linhas == [("1", 2, 2), ("2", 2, 1), ("3", 2, 0)]


def test_regua_por_grupos_polo():
    partidos = np.array(["PT", "PSOL", "PL", "PL", "MDB", None], dtype=object)
    notas = {"PT": 2.0, "PSOL": 1.0, "PL": 9.0, "MDB": 5.0}
    r = ReguaGrupos.montar(partidos, notas)
    assert list(r.esquerda) == [0, 1] and list(r.direita) == [2, 3]
    assert r.nota_esquerda == pytest.approx(1.5) and r.nota_direita == pytest.approx(9.0)
    theta = np.array([-2.0, -1.0, 1.0, 2.0, 0.0, 0.5])
    nota = r.nota_polos(theta)
    # mediana de cada grupo (-1,5 e 1,5) → média das notas do grupo (1,5 e 9,0), linear entre
    assert nota[[0, 1]].mean() == pytest.approx(1.5)
    assert nota[4] == pytest.approx(1.5 + 1.5 * (9.0 - 1.5) / 3.0)  # MDB, fora dos grupos
    assert nota[3] == pytest.approx(10.0)  # extrapolação limitada a 10
    assert not r.polo_unico().any()


def test_regua_indisponivel_sem_um_dos_grupos_e_polo_unico():
    so_direita = ReguaGrupos.montar(np.array(["PL", "MDB"], dtype=object), {"PL": 9, "MDB": 5})
    assert not so_direita.disponivel
    r = ReguaGrupos.montar(np.array(["PT", "PL", "PL"], dtype=object), {"PT": 2, "PL": 9})
    assert list(r.polo_unico()) == [True, False, False]


def test_regua_usa_nota_do_sucessor_de_partido_extinto():
    r = ReguaGrupos.montar(np.array(["PTB"], dtype=object), {"PRD": 8.2})
    assert r.nota_partido[0] == pytest.approx(8.2)


def test_posicoes_na_camara():
    theta = np.array([[0.5, -1.0, 2.0], [-3.0, 0.0, 1.0]])
    assert posicoes_na_camara(theta).tolist() == [[2, 1, 3], [1, 2, 3]]


def test_grupos_de_votacao_separam_so_vizinhos_distinguiveis():
    rng = np.random.default_rng(0)
    # dois vereadores bem à esquerda e três sobrepostos à direita
    centros = np.array([-3.0, -2.95, 1.0, 1.05, 1.1])
    theta = centros + rng.normal(0, 0.3, size=(2000, 5))
    assert grupos_de_votacao(theta).tolist() == [1, 1, 2, 2, 2]


class ServidorSAPL:
    def __init__(self, total=250, informado=None):
        self.registros = [
            {"id": i, "ip": "10.0.0.1", "user": 3, "voto": "Sim"} for i in range(total)
        ]
        self.informado = total if informado is None else informado

    def __call__(self, request: httpx.Request) -> httpx.Response:
        assert request.url.params["o"] == "id"  # ordem estável entre páginas
        pagina = int(request.url.params["page"])
        tamanho = int(request.url.params["page_size"])
        fatia = self.registros[(pagina - 1) * tamanho : pagina * tamanho]
        paginas = -(-self.informado // tamanho)
        return httpx.Response(200, json={
            "pagination": {"total_pages": paginas, "total_entries": self.informado},
            "results": fatia,
        })  # fmt: skip


def test_coleta_pagina_e_descarta_campos_de_auditoria(tmp_path):
    cliente = httpx.Client(transport=httpx.MockTransport(ServidorSAPL()))
    coletor = ColetorSAPL(MUNICIPIO, tmp_path, cliente)
    assert coletor.coletar({"votoparlamentar": "sessao/votoparlamentar"}) == {
        "votoparlamentar": 250
    }
    registros = json.loads((tmp_path / "votoparlamentar.json").read_text())
    assert [r["id"] for r in registros] == list(range(250))
    assert all("ip" not in r and "user" not in r for r in registros)
    manifesto = json.loads((tmp_path / "manifesto.json").read_text())
    assert manifesto["votoparlamentar.json"]["url"].endswith("/api/sessao/votoparlamentar/")


def test_coleta_falha_se_faltarem_registros(tmp_path):
    cliente = httpx.Client(transport=httpx.MockTransport(ServidorSAPL(total=150, informado=250)))
    with pytest.raises(ErroColetaSAPL):
        ColetorSAPL(MUNICIPIO, tmp_path, cliente).coletar({"v": "sessao/votoparlamentar"})


# --- Siscam ---------------------------------------------------------------------------------

ITEM_SISCAM = """
<div class="data-list-item">
  <h4><a href="/Siscam/Votacoes/Details?id={id}">{titulo}</a></h4>
  <p><strong>Sess&#xE3;o Plen&#xE1;ria:</strong>
     <a href="/Siscam/Reunioes/Details?id=814">Sess&#xE3;o Ordin&#xE1;ria N&#xBA; 11/2026</a></p>
  <div class="row"><p class="col-md"><strong>Data:</strong> 01/04/2026</p></div>
  <p class="text-justify"><strong>Ementa:</strong> Algo.</p>
  <p><strong>Autoria: </strong>{autoria}</p>
  <div class="row"><p class="col-md"><strong>Tipo:</strong> Nominal</p>
    <p class="col-md"><strong>Data:</strong> 14/04/2026</p>
    <p class="col-md"><strong>Resultado:</strong> Mantida</p></div>
  {grupos}
</div>"""


def item_siscam(id_, titulo, grupos, autoria="Ana Lima (Ana)"):
    html_grupos = "".join(
        f"<p class='text-justify'><strong>{g} ({len(ns)}):</strong> "
        + ", ".join(f"{n} Civil ({n})" for n in ns)
        + "</p>"
        for g, ns in grupos.items()
    )
    return ITEM_SISCAM.format(id=id_, titulo=titulo, autoria=autoria, grupos=html_grupos)


def pagina_siscam(itens, total=None):
    return (
        "".join(itens)
        + f"<p>{total if total is not None else len(itens)} registros encontrados</p>"
    )


def test_interpreta_listagem_do_siscam():
    pagina = pagina_siscam(
        [
            item_siscam(
                2485,
                "Parecer ao Projeto N&#xBA; 7/2026",
                {"A Favor": ["Ana"], "Contra": ["Bia", "Cris"]},
            )
        ],
        total=1,
    )
    (r,), total = siscam.interpretar_listagem(pagina)
    assert total == 1
    assert r["id"] == 2485 and r["titulo"] == "Parecer ao Projeto Nº 7/2026"
    assert r["data"] == "2026-04-14" and r["data_documento"] == "2026-04-01"
    assert r["id_sessao"] == 814 and r["autoria"] == "Ana Lima (Ana)"
    assert [v["nome"] for v in r["grupos"]["Contra"]] == ["Bia", "Cris"]


def test_listagem_do_siscam_com_contagem_errada_falha():
    pagina = pagina_siscam([item_siscam(1, "Moção Nº 1/2026", {"A Favor": ["Ana"]})])
    pagina = pagina.replace("A Favor (1)", "A Favor (2)")
    with pytest.raises(siscam.ErroColetaSiscam):
        siscam.interpretar_listagem(pagina)


@pytest.mark.parametrize(
    ("titulo", "sigla"),
    [
        ("PLO - Projeto de Lei Ordinária Nº 145/2026", "PLO"),
        ("Projeto de Lei Nº 72/2025", "PLO"),
        ("Projeto de Lei Complementar Nº 2/2024", "PLC"),
        ("RU - Requerimento Urgência Nº 50/2026", "RU"),
        ("REQ - Requerimento Nº 914/2026", "Req"),
        ("EM-Emenda Nº 1/2026 ao PLC - Projeto de Lei Complementar Nº 20/2026", "Emen"),
        ("Moção ao Aplauso Nº 3/2025", "MO"),
        ("Ata Nº 1/2021", "ATA"),
        ("TL - Tribuna Livre Nº 63/2026", None),
    ],
)
def test_classifica_titulo_do_siscam(titulo, sigla):
    assert base_mun.classificar_titulo(titulo)[0] == sigla


def test_base_com_siscam(brutos):
    raiz, especialistas = brutos
    pasta = raiz / "raw" / "teste"
    votacoes = [
        {"id": 7, "titulo": "PLO - Projeto de Lei Ordinária Nº 1/2025", "id_sessao": 3,
         "sessao": "Sessão Plenária Sessão Ordinária Nº 1/2025", "data": "2025-06-10",
         "data_documento": "2025-06-01", "ementa": "Do prefeito", "tipo": "Nominal",
         "autoria": "Poder Executivo, Prefeita", "resultado": "Aprovada",
         "grupos": {"A Favor": [{"nome": "Bia"}, {"nome": "CRIS"}], "Contra": [{"nome": "Ana"}]}},
        {"id": 8, "titulo": "RU - Requerimento Urgência Nº 2/2025", "id_sessao": 3,
         "sessao": "x", "data": "2025-06-10", "data_documento": None, "ementa": None,
         "tipo": "Nominal", "autoria": None, "resultado": None,
         "grupos": {"A Favor": [{"nome": "Ana"}], "Não votaram": [{"nome": "Bia"}]}},
    ]  # fmt: skip
    frequencias = [
        {"id": 1, "titulo": "Expediente", "id_sessao": 3,
         "sessao": "Sessão Plenária Sessão Ordinária Nº 1/2025", "data": "2025-06-10",
         "grupos": {"Presentes": [{"nome": "Ana"}], "Ausências Justificadas": [{"nome": "Bia"}]}},
        {"id": 2, "titulo": "Ordem do Dia", "id_sessao": 3, "sessao": "x", "data": "2025-06-10",
         "grupos": {"Presentes": [{"nome": "Ana"}, {"nome": "Bia"}]}},
    ]  # fmt: skip
    # registro repetido sob outro id: mesmo documento, sessão, dia e votos
    votacoes.append({**votacoes[0], "id": 9})
    # anterior à última votação do SAPL (10/05/2025): o período é do SAPL, fica de fora
    votacoes.append({**votacoes[0], "id": 10, "data": "2025-05-01"})
    _escrever(pasta, "siscam_votacoes", votacoes)
    _escrever(pasta, "siscam_frequencias", frequencias)
    municipio = Municipio(
        "teste", "Teste", "SP", "https://sapl", MUNICIPIO.prefeitos, siscam="https://siscam"
    )
    destino = raiz / "siscam.duckdb"
    base_mun.construir_base([municipio], destino, especialistas, raiz_brutos=raiz / "raw")
    with duckdb.connect(str(destino)) as con:
        assert con.execute(
            """select id_votacao, legislatura, tipo, placar_sim, placar_nao, url
               from votacao where id_votacao like 'siscam-%' order by 1"""
        ).fetchall() == [
            ("siscam-7", 12, "merito", 2, 1, "https://siscam/Siscam/Votacoes/Details?id=7"),
            ("siscam-8", 12, "procedimento", 1, 0, "https://siscam/Siscam/Votacoes/Details?id=8"),
        ]
        # o período do SAPL continua vindo do SAPL
        assert con.execute(
            "select count(*) from votacao where id_votacao not like 'siscam-%'"
        ).fetchone() == (4,)
        # nome parlamentar ligado ao cadastro sem diferenciar maiúsculas e acentos
        assert con.execute(
            "select id_vereador, voto_codificado from voto where id_votacao = 'siscam-7' order by 1"
        ).fetchall() == [("1", 0), ("2", 1), ("3", 1)]
        assert con.execute(
            "select do_executivo, sigla_tipo from materia where id_materia like 'PLO%'"
        ).fetchall() == [(True, "PLO")]
        assert con.execute(
            "select id_vereador from presenca where id_sessao = 'siscam-3' order by 1"
        ).fetchall() == [("1",), ("2",)]


def test_base_com_siscam_recusa_vereador_fora_do_cadastro(brutos):
    raiz, especialistas = brutos
    pasta = raiz / "raw" / "teste"
    _escrever(pasta, "siscam_votacoes", [
        {"id": 7, "titulo": "Moção Nº 1/2025", "id_sessao": None, "sessao": None,
         "data": "2025-06-10", "data_documento": None, "ementa": None, "tipo": "Nominal",
         "autoria": None, "resultado": None, "grupos": {"A Favor": [{"nome": "Desconhecido"}]}},
    ])  # fmt: skip
    _escrever(pasta, "siscam_frequencias", [])
    municipio = Municipio("teste", "Teste", "SP", "x", MUNICIPIO.prefeitos, siscam="y")
    with pytest.raises(ValueError, match="Desconhecido"):
        base_mun.construir_base(
            [municipio], raiz / "s.duckdb", especialistas, raiz_brutos=raiz / "raw"
        )
