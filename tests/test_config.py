from datetime import date

from polaritics.config import GOVERNOS, LEGISLATURAS, governo_em


def test_legislatura_57_cobre_mandato_atual():
    leg = LEGISLATURAS[57]
    assert leg.periodo.anos == [2023, 2024, 2025, 2026, 2027]
    assert leg.periodo.contem(date(2026, 3, 4))
    assert not leg.periodo.contem(date(2027, 2, 1))


def test_governo_em_respeita_transicao():
    assert governo_em(date(2022, 12, 31)).chefe == "Jair Bolsonaro"
    assert governo_em(date(2023, 1, 1)).chefe == "Luiz Inácio Lula da Silva"
    assert governo_em(date(2018, 6, 1)) is None


def test_governos_nao_se_sobrepoem():
    federais = sorted(
        (g for g in GOVERNOS if g.esfera == "federal"), key=lambda g: g.periodo.inicio
    )
    for anterior, seguinte in zip(federais, federais[1:], strict=False):
        assert anterior.periodo.fim < seguinte.periodo.inicio
