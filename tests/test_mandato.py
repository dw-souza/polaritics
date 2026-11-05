"""Cenário calculado à mão para gastos, presença e atividade (medidas/mandato.py).

- A (SP): em exercício de 01/02 a 30/04/2023; gasta 1.000, 2.000 e 3.000 em fev, mar e abr.
- B (RR): em exercício de 01 a 14/02 (meio fevereiro) e de 01/03 a 30/04; gasta 500, 1.000, 1.000.
- Sessões em 10/02, 20/02 (B fora do exercício) e 10/03.
"""

from datetime import date

import duckdb
import pytest

from polaritics.base.carga import ESQUEMA
from polaritics.medidas.mandato import calcular_atividade, calcular_gastos, calcular_presenca


@pytest.fixture
def con():
    c = duckdb.connect()
    c.execute(ESQUEMA.read_text(encoding="utf-8"))
    c.execute("insert into legislatura values (57, '2023-02-01', '2027-01-31')")
    c.executemany(
        "insert into exercicio values (?, 57, ?, ?)",
        [
            ("A", date(2023, 2, 1), date(2023, 4, 30)),
            ("B", date(2023, 2, 1), date(2023, 2, 14)),
            ("B", date(2023, 3, 1), date(2023, 4, 30)),
        ],
    )
    c.executemany(
        "insert into despesa values (?, ?, 2023, ?, ?, ?, ?, ?)",
        [
            ("A", "SP", 2, "TELEFONIA", "Tele SA", "11222333000144", 1000.0),
            ("A", "SP", 3, "TELEFONIA", "Tele SA", "11222333000144", 2000.0),
            ("A", "SP", 4, "COMBUSTÍVEIS E LUBRIFICANTES.", "Fulano", "12345678901", 3000.0),
            ("B", "RR", 2, "TELEFONIA", "Tele SA", "11222333000144", 500.0),
            ("B", "RR", 3, "TELEFONIA", "Tele SA", "11222333000144", 1000.0),
            ("B", "RR", 4, "TELEFONIA", "Tele SA", "11222333000144", 1000.0),
        ],
    )
    c.executemany("insert into cota_uf values (?, ?)", [("SP", 40000.0), ("RR", 50000.0)])
    c.executemany(
        "insert into sessao values (?, ?)",
        [("s1", date(2023, 2, 10)), ("s2", date(2023, 2, 20)), ("s3", date(2023, 3, 10))],
    )
    c.executemany(
        "insert into presenca values (?, ?)",
        [("s1", "A"), ("s3", "A"), ("s1", "B"), ("s3", "B"), ("s2", "B")],
    )
    c.executemany(
        "insert into proposicao values (?, ?, ?, 2023, ?, ?)",
        [
            ("p1", "PL", "1", "Lei", "Transformado em Norma Jurídica"),
            ("p2", "PL", "2", "Parado", "Aguardando Parecer"),
            ("p3", "PEC", "3", "No Senado", "Aguardando Apreciação pelo Senado Federal"),
        ],
    )
    c.executemany(
        "insert into autoria values (?, ?, ?, ?)",
        [("p1", "A", 1, True), ("p2", "A", 1, True), ("p1", "B", 2, True), ("p3", "B", 1, True)],
    )
    calcular_gastos(c, 57)
    calcular_presenca(c, 57)
    calcular_atividade(c, 57)
    yield c
    c.close()


def test_gastos_por_mes_em_exercicio_e_relativo_a_cota_do_estado(con):
    linhas = con.execute(
        """select id_camara, uf, meses, total, por_mes, relativo, suficiente
           from gastos where ano is null order by id_camara"""
    ).fetchall()
    a, b = linhas
    assert a[:4] == ("A", "SP", pytest.approx(3.0), pytest.approx(6000.0))
    assert a[4] == pytest.approx(2000.0) and a[5] == pytest.approx(2000 / 40000) and a[6]
    # fevereiro conta meio mês (14 de 28 dias)
    assert b[:4] == ("B", "RR", pytest.approx(2.5), pytest.approx(2500.0))
    assert b[4] == pytest.approx(1000.0) and b[5] == pytest.approx(1000 / 50000) and not b[6]


def test_fornecedor_pessoa_fisica_sem_nome(con):
    nomes = {f for (f,) in con.execute("select fornecedor from gastos_fornecedor").fetchall()}
    assert nomes == {"Tele SA", "Pessoa física"}


def test_presenca_conta_so_sessoes_em_exercicio(con):
    linhas = con.execute(
        """select id_camara, sessoes, presentes from presenca_plenario
           where ano is null order by id_camara"""
    ).fetchall()
    # s2 ficou de fora para B (fora do exercício), mesmo com presença registrada
    assert linhas == [("A", 3, 2), ("B", 2, 2)]


def test_atividade_so_conta_primeiro_autor(con):
    linhas = con.execute(
        """select id_camara, apresentados, aprovados_camara, viraram_lei
           from atividade order by id_camara"""
    ).fetchall()
    assert linhas == [("A", 2, 1, 1), ("B", 1, 1, 0)]
    aprovadas = con.execute(
        "select id_camara, id from atividade_aprovadas order by 1, 2"
    ).fetchall()
    assert aprovadas == [("A", "p1"), ("B", "p3")]
