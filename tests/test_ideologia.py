import numpy as np
import pytest

from polaritics.medidas.ideologia import escala, irt
from polaritics.medidas.ideologia.faixas import faixa


@pytest.mark.parametrize(
    ("nota", "esperado"),
    [
        (0.0, "Mais à esquerda"),
        (1.50, "Mais à esquerda"),
        (1.51, "Esquerda"),
        (3.00, "Esquerda"),
        (4.49, "Centro-esquerda"),
        (4.50, "Centro"),
        (5.50, "Centro"),
        (5.51, "Centro-direita"),
        (7.00, "Centro-direita"),
        (8.50, "Direita"),
        (8.51, "Mais à direita"),
        (10.0, "Mais à direita"),
        (12.0, "Mais à direita"),
        (-1.0, "Mais à esquerda"),
    ],
)
def test_faixa_nos_cortes_do_instrumento(nota, esperado):
    assert faixa(nota) == esperado


def test_ajustar_polos_fixa_so_os_dois_partidos_de_referencia():
    f = escala.ajustar_polos(-1.5, 2.7, 1.5, 8.8)
    assert f(np.array([-1.5, 1.5])) == pytest.approx([2.7, 8.8])
    assert f(np.array([0.0]))[0] == pytest.approx((2.7 + 8.8) / 2)  # linear entre os polos
    assert f(np.array([2.0]))[0] == pytest.approx(8.8 + 0.5 * 6.1 / 3)  # extrapola
    assert f(np.array([-10.0, 10.0])) == pytest.approx([0.0, 10.0])  # limita a [0, 10]


def test_ajustar_polos_rejeita_polos_invertidos():
    with pytest.raises(ValueError):
        escala.ajustar_polos(1.0, 2.7, -1.0, 8.8)


def test_ajustar_isotonico_e_monotonico_e_forma_plato_quando_ordem_diverge():
    # partido B vota à direita de C, mas especialistas o põem à esquerda: platô entre eles
    theta = np.array([-1.0, 0.0, 0.5, 1.0])
    notas = np.array([2.0, 6.0, 5.0, 9.0])
    f = escala.ajustar(theta, notas, pesos=np.array([1.0, 1.0, 1.0, 1.0]))
    valores = f(np.linspace(-2, 2, 50))
    assert np.all(np.diff(valores) >= -1e-12)
    assert f(np.array([0.0]))[0] == pytest.approx(f(np.array([0.5]))[0])
    assert f(np.array([-1.0, 1.0])) == pytest.approx([2.0, 9.0])


def test_ajustar_isotonico_rejeita_ordem_oposta():
    with pytest.raises(ValueError):
        escala.ajustar(np.array([-1.0, 1.0]), np.array([8.0, 2.0]), np.array([1.0, 1.0]))


def simular(n_dep=40, n_vot=80, semente=0):
    rng = np.random.default_rng(semente)
    theta = np.linspace(-2, 2, n_dep)
    alpha, beta = rng.normal(0, 1, n_vot), rng.normal(0, 2, n_vot)
    i_dep, i_vot = np.meshgrid(np.arange(n_dep), np.arange(n_vot), indexing="ij")
    i_dep, i_vot = i_dep.ravel(), i_vot.ravel()
    observado = rng.random(i_dep.size) > 0.2  # 20% de ausências
    i_dep, i_vot = i_dep[observado], i_vot[observado]
    p = 1 / (1 + np.exp(-(beta[i_vot] * theta[i_dep] - alpha[i_vot])))
    y = (rng.random(p.size) < p).astype(np.float32)
    m = irt.MatrizVotos(
        [f"d{i}" for i in range(n_dep)], [f"v{j}" for j in range(n_vot)], i_dep, i_vot, y
    )
    return m, theta


def test_irt_recupera_ordem_e_sinal_em_dados_simulados():
    m, theta_real = simular()
    esquerda, direita = np.arange(0, 10), np.arange(30, 40)
    r = irt.estimar(m, esquerda, direita, aquecimento=300, amostras=300, cadeias=2, semente=1)
    estimado = np.median(r.theta, axis=0)
    assert np.corrcoef(estimado, theta_real)[0, 1] > 0.95
    assert estimado[esquerda].mean() < estimado[direita].mean()
    assert r.theta.shape == (600, 40)
    assert np.allclose(r.theta.mean(axis=1), 0, atol=1e-5)  # padronizado por amostra
    assert r.rhat_max < 1.05
