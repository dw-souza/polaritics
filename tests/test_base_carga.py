import csv

import duckdb
import pytest

from polaritics.base.carga import construir_base


def escrever(caminho, linhas):
    with caminho.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]), delimiter=";", quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(linhas)


def votacao(id_, data, descricao, orgao="PLEN"):
    return {
        "id": id_,
        "data": data,
        "dataHoraRegistro": f"{data}T18:00:00",
        "siglaOrgao": orgao,
        "descricao": descricao,
    }


def voto(id_votacao, dep, data_hora, voto_, partido):
    return {
        "idVotacao": id_votacao,
        "dataHoraVoto": data_hora,
        "voto": voto_,
        "deputado_id": dep,
        "deputado_siglaPartido": partido,
        "deputado_siglaUf": "SP",
    }


@pytest.fixture
def base(tmp_path):
    brutos = tmp_path / "raw"
    brutos.mkdir()
    escrever(
        brutos / "deputados.csv",
        [
            {
                "uri": "https://x/deputados/1",
                "nome": "Ana",
                "idLegislaturaFinal": "57",
                "nomeCivil": "Ana Silva",
                "cpf": "111",
                "siglaSexo": "F",
                "dataNascimento": "1980-01-02",
            },
            {
                "uri": "https://x/deputados/2",
                "nome": "Bia",
                "idLegislaturaFinal": "57",
                "nomeCivil": "",
                "cpf": "",
                "siglaSexo": "F",
                "dataNascimento": "",
            },
            {
                "uri": "https://x/deputados/9",
                "nome": "Antigo",
                "idLegislaturaFinal": "50",
                "nomeCivil": "",
                "cpf": "",
                "siglaSexo": "M",
                "dataNascimento": "",
            },
        ],
    )
    escrever(
        brutos / "votacoes-2024.csv",
        [
            votacao(
                "v1", "2024-03-01", "Aprovado o Projeto de Lei nº 1. Sim: 1; Não: 1; Total: 2."
            ),
            votacao("v2", "2024-04-10", "Rejeitado o Requerimento. Sim: 1; Não: 1; Total: 2."),
            votacao("v3", "2024-05-01", "Votos: Sr. Fulano: Sim: 2; Total: 2."),
            votacao("v4", "2024-05-02", "Aprovado o Requerimento."),
        ],
    )
    escrever(
        brutos / "votacoesVotos-2024.csv",
        [
            voto("v1", "1", "2024-03-01T18:01:00", "Sim", "PATRIOTA"),
            voto("v1", "2", "2024-03-01T18:01:00", "Obstrução", "S.PART."),
            voto("v2", "1", "2024-04-10T18:01:00", "Não", "PRD"),
            voto("v2", "1", "2024-04-10T18:00:00", "Sim", "PRD"),  # registro anterior duplicado
            voto("v2", "2", "2024-04-10T18:01:00", "Abstenção", "PC do B"),
            voto("v3", "1", "2024-05-01T18:01:00", "", "PRD"),
        ],
    )
    escrever(
        brutos / "votacoesOrientacoes-2024.csv",
        [
            {"idVotacao": "v1", "siglaBancada": "Governo", "orientacao": "Obstrução"},
            {"idVotacao": "v1", "siglaBancada": "Oposição", "orientacao": "Liberado"},
        ],
    )
    caminho = construir_base(brutos, tmp_path / "base.duckdb")
    with duckdb.connect(str(caminho), read_only=True) as con:
        yield con


def test_carrega_so_deputados_das_legislaturas_configuradas(base):
    assert base.sql("select id_camara, cpf from deputado order by 1").fetchall() == [
        ("1", "111"),
        ("2", None),
    ]


def test_votacoes_classificadas_e_marcadas(base):
    linhas = base.sql("""select id, nominal, sem_votos_individuais, tipo, legislatura
                         from votacao order by id""").fetchall()
    assert linhas == [
        ("v1", True, False, "merito", 57),
        ("v2", True, False, "procedimento", 57),
        ("v3", True, True, "eleicao", 57),
        ("v4", False, False, "procedimento", 57),
    ]


def test_votos_codificados_e_partido_harmonizado(base):
    linhas = base.sql("""select id_votacao, id_camara, voto_original, voto_codificado, partido
                         from voto order by 1, 2""").fetchall()
    assert linhas == [
        ("v1", "1", "Sim", 1, "PATRIOTA"),
        ("v1", "2", "Obstrução", 0, None),
        ("v2", "1", "Não", 0, "PRD"),  # fica o registro mais recente
        ("v2", "2", "Abstenção", None, "PCdoB"),
        ("v3", "1", None, None, "PRD"),
    ]


def test_orientacao_codificada(base):
    assert base.sql(
        "select bancada, orientacao_codificada from orientacao order by 1"
    ).fetchall() == [("Governo", 0), ("Oposição", None)]


def test_filiacao_em_periodos(base):
    linhas = base.sql("""select id_camara, partido, inicio::varchar, fim::varchar
                         from filiacao order by 1, 3""").fetchall()
    assert linhas == [
        ("1", "PATRIOTA", "2024-03-01", "2024-03-01"),
        ("1", "PRD", "2024-04-10", "2024-05-01"),
        ("2", None, "2024-03-01", "2024-03-01"),
        ("2", "PCdoB", "2024-04-10", "2024-04-10"),
    ]
