import pytest

from polaritics.base import partidos
from polaritics.base.votacoes import (
    ELEICAO,
    INDEFINIDO,
    MERITO,
    PROCEDIMENTO,
    classificar_votacao,
    codificar_voto,
    eh_nominal,
)


@pytest.mark.parametrize(
    ("descricao", "esperado"),
    [
        ("Rejeitado o Requerimento. Sim: 120; Não: 300; Total: 420.", PROCEDIMENTO),
        (
            "Aprovado o Requerimento de Urgência (Art. 155 do RICD). Sim: 299; Total: 410.",
            PROCEDIMENTO,
        ),
        (
            "Rejeitado o Recurso nº 2, de 2026, contra parecer terminativo. Total: 398.",
            PROCEDIMENTO,
        ),
        ("Aprovada a Preferência. Sim: 300; Total: 400.", PROCEDIMENTO),
        ("Rejeitada a inclusão. Sim: 100; Total: 400.", PROCEDIMENTO),
        (
            "Aprovado, em apreciação preliminar, o atendimento dos pressupostos. Total: 400.",
            PROCEDIMENTO,
        ),
        ("Aprovado o Projeto de Lei nº 3.802, de 2024. Sim: 340; Total: 458.", MERITO),
        (
            "Aprovado, em primeiro turno, o Substitutivo à Proposta de Emenda à "
            "Constituição nº 18, de 2025. Sim: 487; Não: 15; Total: 503.",
            MERITO,
        ),
        ("Aprovada, em segundo turno, a Proposta de Emenda à Constituição nº 18.", MERITO),
        ("Mantido o texto. Sim: 205; Não: 91; Total: 297.", MERITO),
        ("Suprimido o texto. Sim: 100; Total: 300.", MERITO),
        ("Rejeitada a Emenda de Plenário n° 7. Sim: 187; não: 202; total: 390.", MERITO),
        ("Aprovada a Redação Final. Sim: 300; Total: 400.", MERITO),
        ("Votos: \r\nSra. Daiane Nogueira de Lira: \r\nSim: 388;\r\nTotal: 421.", ELEICAO),
        ("Resultado. Sim: 182; Não: 182; Total: 366.", INDEFINIDO),
    ],
)
def test_classificar_votacao(descricao, esperado):
    assert classificar_votacao(descricao) == esperado


def test_eh_nominal():
    assert eh_nominal("Aprovado. Sim: 300; Não: 100; Total: 400.")
    assert eh_nominal("Rejeitado. sim: 1; total: 2.")
    assert not eh_nominal("Aprovado o Requerimento.")


@pytest.mark.parametrize(
    ("voto", "codigo"),
    [
        ("Sim", 1),
        ("Não", 0),
        ("Obstrução", 0),  # decisão D1
        ("Abstenção", None),
        ("Artigo 17", None),
        ("", None),
        (None, None),
    ],
)
def test_codificar_voto(voto, codigo):
    assert codificar_voto(voto) == codigo


def test_harmonizar_partido():
    assert partidos.harmonizar("PC do B") == "PCdoB"
    assert partidos.harmonizar("Novo") == "NOVO"
    assert partidos.harmonizar("PT") == "PT"
    assert partidos.harmonizar("S.PART.") is None
    assert partidos.harmonizar(None) is None


def test_sucessor_atual_segue_fusoes():
    assert partidos.sucessor_atual("PATRIOTA") == "PRD"
    assert partidos.sucessor_atual("PTB") == "PRD"
    assert partidos.sucessor_atual("PSC") == "PODE"
    assert partidos.sucessor_atual("PT") == "PT"
