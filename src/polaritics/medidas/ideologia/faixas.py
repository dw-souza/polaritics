"""Faixas fixas da escala 0–10 (metodologia, seção 4.3; cortes do instrumento dos especialistas)."""

import numpy as np

# (limite superior inclusivo, rótulo)
FAIXAS = [
    (1.50, "Mais à esquerda"),
    (3.00, "Esquerda"),
    (4.49, "Centro-esquerda"),
    (5.50, "Centro"),
    (7.00, "Centro-direita"),
    (8.50, "Direita"),
    (10.00, "Mais à direita"),
]
_LIMITES = np.array([limite for limite, _ in FAIXAS])
ROTULOS = [rotulo for _, rotulo in FAIXAS]


def faixa(nota: float) -> str:
    """Faixa da nota, arredondada a duas casas como os cortes do instrumento."""
    nota = round(min(max(nota, 0.0), 10.0), 2)
    return ROTULOS[int(np.searchsorted(_LIMITES, nota, side="left"))]
