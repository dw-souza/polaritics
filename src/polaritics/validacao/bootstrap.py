"""Estabilidade da faixa por bootstrap das votações (metodologia, seção 8) e zona de fronteira
(seção 4.3.1).

Reamostrar votações e reestimar por MCMC custaria horas por réplica. Por isso cada réplica usa
a moda a posteriori (MAP) do mesmo modelo, que reproduz o MCMC com correlação de 0,9999 nesta
base. O teste mede o quanto a faixa depende de *quais* votações entraram, não a incerteza do
modelo, que já aparece no intervalo de 90% publicado.
"""

import logging
from collections import Counter
from dataclasses import dataclass

import numpy as np

from polaritics.medidas.ideologia import irt
from polaritics.medidas.ideologia.calculo import Referencias
from polaritics.medidas.ideologia.faixas import ROTULOS, faixa

log = logging.getLogger(__name__)

MIN_REPLICAS_MESMA_FAIXA = 0.80


def _reamostrar(m: irt.MatrizVotos, rng: np.random.Generator) -> irt.MatrizVotos:
    n_vot = m.forma[1]
    ordem = np.argsort(m.i_vot, kind="stable")
    inicio = np.searchsorted(m.i_vot[ordem], np.arange(n_vot + 1))
    sorteadas = rng.integers(0, n_vot, n_vot)
    blocos = [ordem[inicio[j] : inicio[j + 1]] for j in sorteadas]
    obs = np.concatenate(blocos)
    novo_item = np.repeat(np.arange(n_vot), [len(b) for b in blocos])
    return irt.MatrizVotos(m.deputados, m.votacoes, m.i_dep[obs], novo_item, m.y[obs])


def faixas(ref: Referencias, theta: np.ndarray) -> np.ndarray:
    return np.array([faixa(n) for n in ref.nota_polos(theta)])


def faixas_bootstrap(
    m: irt.MatrizVotos, ref: Referencias, replicas: int = 100, semente: int = 7
) -> np.ndarray:
    """Faixa de cada deputado em cada réplica: matriz (réplicas, deputados)."""
    rng = np.random.default_rng(semente)
    resultado = np.empty((replicas, m.forma[0]), dtype=object)
    for k in range(replicas):
        resultado[k] = faixas(ref, irt.estimar_map(_reamostrar(m, rng), ref.esquerda, ref.direita))
        if (k + 1) % 10 == 0:
            log.info("bootstrap %d/%d", k + 1, replicas)
    return resultado


@dataclass(frozen=True)
class Exibicao:
    faixa_publicada: str
    fracao_mesma_faixa: float  # réplicas com a faixa publicada
    fronteira: bool
    faixas_exibidas: tuple[str, ...]  # uma faixa, ou duas em ordem da escala
    cobertura: float  # réplicas cuja faixa está entre as exibidas

    @property
    def rotulo(self) -> str:
        if not self.fronteira:
            return self.faixa_publicada
        a, b = self.faixas_exibidas
        return f"Entre {a.lower()} e {b.lower()}"


def exibir(faixa_publicada: str, faixas_replicas) -> Exibicao:
    """Decide se o deputado é exibido com uma faixa ou em zona de fronteira."""
    contagem = Counter(faixas_replicas)
    total = sum(contagem.values())
    mesma = contagem[faixa_publicada] / total
    if mesma >= MIN_REPLICAS_MESMA_FAIXA:
        return Exibicao(faixa_publicada, mesma, False, (faixa_publicada,), mesma)
    vizinha = max((f for f in contagem if f != faixa_publicada), key=contagem.get)
    exibidas = tuple(sorted((faixa_publicada, vizinha), key=ROTULOS.index))
    cobertura = sum(contagem[f] for f in exibidas) / total
    return Exibicao(faixa_publicada, mesma, True, exibidas, cobertura)
