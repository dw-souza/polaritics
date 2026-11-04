"""Cenário calculado à mão: deputados 1–3 do PT, 4–5 do PL, votações em 2024 (governo Lula).

| votação | tipo     | Governo  | Oposição | 1   | 2   | 3   | 4   | 5          |
|---------|----------|----------|----------|-----|-----|-----|-----|------------|
| a       | mérito   | Sim      | Não      | Sim | Sim | Não | Não | Obstrução  |
| b       | mérito   | Sim      | Sim      | Sim | Sim | Sim | Sim | Abstenção  |
| c       | proced.  | Liberado | Não      | Sim | Não | Não | Sim | Sim        |
| d       | eleição  | Não      | —        | Sim | Sim | Sim | Sim | Sim        |
"""

import duckdb
import pytest
from conftest import deputado, escrever_brutos, orientacao, votacao, voto

from polaritics.base.carga import construir_base
from polaritics.medidas.fidelidade import calcular_fidelidade
from polaritics.medidas.governismo import calcular_governismo

PARTIDO = {"1": "PT", "2": "PT", "3": "PT", "4": "PL", "5": "PL"}
VOTOS = {
    "a": ["Sim", "Sim", "Não", "Não", "Obstrução"],
    "b": ["Sim", "Sim", "Sim", "Sim", "Abstenção"],
    "c": ["Sim", "Não", "Não", "Sim", "Sim"],
    "d": ["Sim", "Sim", "Sim", "Sim", "Sim"],
}
DATAS = {"a": "2024-03-01", "b": "2024-03-02", "c": "2024-03-03", "d": "2024-03-04"}
PLACAR = "Sim: 3; Não: 2; Total: 5."


@pytest.fixture
def con(tmp_path):
    brutos = escrever_brutos(
        tmp_path / "raw",
        deputados=[deputado(d) for d in PARTIDO],
        votacoes=[
            votacao("a", DATAS["a"], f"Aprovado o Projeto de Lei nº 1. {PLACAR}"),
            votacao("b", DATAS["b"], f"Aprovado o Projeto de Lei nº 2. {PLACAR}"),
            votacao("c", DATAS["c"], f"Aprovado o Requerimento. {PLACAR}"),
            votacao("d", DATAS["d"], f"Votos: Sr. Fulano: {PLACAR}"),
        ],
        votos=[
            voto(v, dep, f"{DATAS[v]}T18:01:00", votos[i], PARTIDO[dep])
            for v, votos in VOTOS.items()
            for i, dep in enumerate(PARTIDO)
        ],
        orientacoes=[
            orientacao("a", "Governo", "Sim"),
            orientacao("a", "Oposição", "Não"),
            orientacao("b", "Governo", "Sim"),
            orientacao("b", "Oposição", "Sim"),
            orientacao("c", "Governo", "Liberado"),
            orientacao("c", "Oposição", "Não"),
            orientacao("d", "Governo", "Não"),
        ],
    )
    caminho = construir_base(brutos, tmp_path / "base.duckdb")
    with duckdb.connect(str(caminho)) as conexao:
        calcular_governismo(conexao)
        calcular_fidelidade(conexao)
        yield conexao


def test_governismo_total_e_disputado(con):
    linhas = con.sql("""
        select id_camara, governo, n_total, alinhados_total, n_disputadas, alinhados_disputadas
        from governismo where ano is null order by id_camara
    """).fetchall()
    lula = "Luiz Inácio Lula da Silva"
    assert linhas == [
        ("1", lula, 2, 2, 1, 1),
        ("2", lula, 2, 2, 1, 1),
        ("3", lula, 2, 1, 1, 0),
        ("4", lula, 2, 1, 1, 0),
        ("5", lula, 1, 0, 1, 0),  # obstrução = Não; abstenção fora do denominador
    ]


def test_governismo_por_ano_e_suficiencia(con):
    assert con.execute("select count(*) from governismo where ano = 2024").fetchone()[0] == 5
    assert con.execute("select bool_or(suficiente) from governismo").fetchone()[0] is False


def test_fidelidade_pela_maioria_dos_outros_do_partido(con):
    linhas = con.sql("""
        select id_camara, n, alinhados from fidelidade where ano is null order by id_camara
    """).fetchall()
    # PL tem só 2 votos por votação (< 3): fora. Empates da maioria dos outros: fora.
    assert linhas == [("1", 2, 1), ("2", 1, 1), ("3", 2, 1)]
