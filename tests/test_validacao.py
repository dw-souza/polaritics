import numpy as np

from polaritics.medidas.ideologia import irt
from polaritics.validacao import bootstrap
from polaritics.validacao.criterios import Resultado, _familia, publicavel


def resultado(status, variante=None, obrigatorio=True):
    return Resultado("c", variante, None, "", status, "", obrigatorio)


def test_publicavel_exige_todos_os_obrigatorios_aprovados():
    base = [resultado("aprovado"), resultado("aprovado", "todas")]
    assert publicavel(base, "todas")
    assert not publicavel([*base, resultado("pendente", "todas")], "todas")
    assert not publicavel([*base, resultado("reprovado")], "todas")


def test_publicavel_ignora_outra_variante_e_nao_obrigatorios():
    base = [resultado("aprovado", "todas")]
    assert publicavel([*base, resultado("reprovado", "merito")], "todas")
    assert publicavel([*base, resultado("pendente", "todas", obrigatorio=False)], "todas")
    assert publicavel([*base, resultado("informativo", "todas", obrigatorio=False)], "todas")


def test_familia_usa_cortes_do_gps():
    assert [_familia(n) for n in (4.49, 4.5, 7.0, 7.01)] == [
        "esquerda",
        "centro",
        "centro",
        "direita",
    ]


def test_reamostrar_mantem_votacoes_inteiras():
    m = irt.MatrizVotos(
        ["a", "b"],
        ["v0", "v1", "v2"],
        np.array([0, 1, 0, 1, 0]),
        np.array([0, 0, 1, 1, 2]),
        np.array([1, 0, 1, 1, 0], dtype=np.float32),
    )
    mb = bootstrap._reamostrar(m, np.random.default_rng(3))
    assert mb.forma == m.forma
    # cada votação sorteada traz todos os seus votos; a contagem por item vem do original
    tamanhos_originais = np.bincount(m.i_vot, minlength=3)
    assert set(np.bincount(mb.i_vot, minlength=3)) <= set(tamanhos_originais) | {0}
    assert len(mb.y) == sum(np.bincount(mb.i_vot, minlength=3))


def test_exibir_faixa_unica_quando_estavel():
    e = bootstrap.exibir("Centro", ["Centro"] * 85 + ["Centro-direita"] * 15)
    assert not e.fronteira
    assert e.rotulo == "Centro"
    assert e.cobertura == 0.85


def test_exibir_fronteira_com_par_em_ordem_da_escala():
    e = bootstrap.exibir(
        "Centro-direita", ["Centro"] * 45 + ["Centro-direita"] * 50 + ["Direita"] * 5
    )
    assert e.fronteira
    assert e.faixas_exibidas == ("Centro", "Centro-direita")
    assert e.rotulo == "Entre centro e centro-direita"
    assert e.cobertura == 0.95
    assert e.fracao_mesma_faixa == 0.50
