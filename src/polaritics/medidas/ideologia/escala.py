"""Tradução da posição IRT para a escala 0–10 dos especialistas (metodologia, seção 4.2).

Duas réguas, calculadas sobre as mesmas amostras do modelo:

- `ajustar_polos` (visão principal, "comportamento de voto"): linear, fixada só pelos dois
  partidos de referência (o maior de cada polo). Todos os outros partidos e deputados se
  posicionam apenas pelos votos, o que permite comparar "o que o partido diz ser" (nota dos
  especialistas) com "como vota".
- `ajustar` (visão secundária, "dentro do campo do partido"): monotônica por partes.
  Regressão isotônica (ponderada pelo tamanho da bancada) das notas dos especialistas sobre a
  mediana IRT de cada partido de referência, com interpolação linear entre os pontos. Cada
  partido fica perto da própria nota, e o deputado aparece mais à esquerda ou à direita dele.

Fora do intervalo dos nós, as duas extrapolam linearmente e limitam a [0, 10].
"""

from dataclasses import dataclass

import numpy as np
from scipy.optimize import isotonic_regression


@dataclass(frozen=True)
class Transformacao:
    x: np.ndarray  # nós (posição IRT), crescentes
    y: np.ndarray  # nota 0–10 em cada nó, não decrescente
    inclinacao: float

    def __call__(self, theta: np.ndarray) -> np.ndarray:
        theta = np.asarray(theta, dtype=float)
        nota = np.interp(theta, self.x, self.y)
        nota = np.where(theta < self.x[0], self.y[0] + self.inclinacao * (theta - self.x[0]), nota)
        nota = np.where(
            theta > self.x[-1], self.y[-1] + self.inclinacao * (theta - self.x[-1]), nota
        )
        return np.clip(nota, 0.0, 10.0)


def ajustar_polos(
    theta_esq: float, nota_esq: float, theta_dir: float, nota_dir: float
) -> Transformacao:
    if theta_dir <= theta_esq:
        raise ValueError("o polo de direita ficou à esquerda do de esquerda nos votos")
    inclinacao = (nota_dir - nota_esq) / (theta_dir - theta_esq)
    return Transformacao(
        np.array([theta_esq, theta_dir]), np.array([nota_esq, nota_dir]), inclinacao
    )


def ajustar(theta_partidos: np.ndarray, notas: np.ndarray, pesos: np.ndarray) -> Transformacao:
    ordem = np.argsort(theta_partidos)
    x, y, w = theta_partidos[ordem], notas[ordem], pesos[ordem]
    ajustado = isotonic_regression(y, weights=w, increasing=True).x
    inclinacao = float(np.polyfit(x, y, 1, w=np.sqrt(w))[0])
    if inclinacao <= 0:
        raise ValueError("a ordem dos partidos nos votos é oposta à dos especialistas")
    # nós com o mesmo x (empate de medianas) viram um só, com a média ponderada
    xs, inverso = np.unique(x, return_inverse=True)
    ys = np.bincount(inverso, weights=ajustado * w) / np.bincount(inverso, weights=w)
    if len(xs) == 1:
        xs, ys = np.array([xs[0], xs[0] + 1e-9]), np.repeat(ys, 2)
    return Transformacao(xs, np.maximum.accumulate(ys), inclinacao)
