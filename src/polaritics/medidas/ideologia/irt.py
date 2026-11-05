"""Modelo IRT unidimensional bayesiano (2 parâmetros) estimado por NUTS no NumPyro.

P(voto Sim) = logística(beta_j * theta_i - alpha_j), com theta_i ~ N(0, 1),
alpha_j ~ N(0, 5) e beta_j ~ N(0, 2,5).

Identificação: a escala de theta é fixada por padronização a cada amostra (média 0, desvio 1)
e o sinal pela comparação entre os grupos de referência (esquerda < direita), em cada cadeia.
As cadeias partem de um valor inicial dado pelo primeiro componente da SVD da matriz de votos,
o que evita que caiam no modo espelhado.
"""

from dataclasses import dataclass

import jax
import jax.numpy as jnp
import numpy as np
import numpyro
import numpyro.distributions as dist
from numpyro.diagnostics import effective_sample_size, split_gelman_rubin
from numpyro.infer import MCMC, NUTS, init_to_value


@dataclass(frozen=True)
class MatrizVotos:
    deputados: list[str]
    votacoes: list[str]
    i_dep: np.ndarray
    i_vot: np.ndarray
    y: np.ndarray  # 1 = Sim, 0 = Não/Obstrução

    @property
    def forma(self) -> tuple[int, int]:
        return len(self.deputados), len(self.votacoes)


@dataclass(frozen=True)
class Resultado:
    theta: np.ndarray  # (amostras, deputados), padronizado e com sinal alinhado
    alpha: np.ndarray  # (amostras, votacoes)
    beta: np.ndarray  # (amostras, votacoes)
    rhat_max: float
    ess_min: float
    divergencias: int


def modelo(i_dep, i_vot, n_dep, n_vot, y=None):
    theta = numpyro.sample("theta", dist.Normal(0.0, 1.0).expand([n_dep]))
    alpha = numpyro.sample("alpha", dist.Normal(0.0, 5.0).expand([n_vot]))
    beta = numpyro.sample("beta", dist.Normal(0.0, 2.5).expand([n_vot]))
    logits = beta[i_vot] * theta[i_dep] - alpha[i_vot]
    numpyro.sample("y", dist.Bernoulli(logits=logits), obs=y)


def valor_inicial(m: MatrizVotos, esquerda: np.ndarray, direita: np.ndarray) -> np.ndarray:
    """Primeiro componente da SVD da matriz (faltantes = média da votação), padronizado."""
    n_dep, n_vot = m.forma
    soma = np.bincount(m.i_vot, weights=m.y, minlength=n_vot)
    media = soma / np.bincount(m.i_vot, minlength=n_vot)
    denso = np.tile(media, (n_dep, 1))
    denso[m.i_dep, m.i_vot] = m.y
    u, s, _ = np.linalg.svd(denso - denso.mean(axis=0), full_matrices=False)
    x = u[:, 0] * s[0]
    x = (x - x.mean()) / x.std()
    return -x if x[esquerda].mean() > x[direita].mean() else x


def estimar_map(
    m: MatrizVotos, esquerda: np.ndarray, direita: np.ndarray, max_iter: int = 2000
) -> np.ndarray:
    """Moda a posteriori do mesmo modelo (mesmas prioris), por L-BFGS. Muito mais rápida que o
    MCMC e sem incerteza: usada no bootstrap de estabilidade, não nos resultados publicados.
    Retorna theta padronizado e com o sinal alinhado."""
    from scipy.optimize import minimize

    n_dep, n_vot = m.forma
    D, V, y = m.i_dep, m.i_vot, m.y.astype(float)

    def objetivo(p):
        theta, alpha, beta = p[:n_dep], p[n_dep : n_dep + n_vot], p[n_dep + n_vot :]
        eta = beta[V] * theta[D] - alpha[V]
        r = 1 / (1 + np.exp(-eta)) - y
        nll = np.sum(np.logaddexp(0, eta) - y * eta)
        prior = 0.5 * theta @ theta + alpha @ alpha / 50 + beta @ beta / 12.5
        grad = np.concatenate(
            [
                np.bincount(D, r * beta[V], n_dep) + theta,
                np.bincount(V, -r, n_vot) + alpha / 25,
                np.bincount(V, r * theta[D], n_vot) + beta / 6.25,
            ]
        )
        return nll + prior, grad

    inicio = valor_inicial(m, esquerda, direita)
    p0 = np.concatenate([inicio, np.zeros(n_vot), np.full(n_vot, 0.1)])
    p = minimize(objetivo, p0, jac=True, method="L-BFGS-B", options={"maxiter": max_iter}).x
    theta = p[:n_dep]
    theta = (theta - theta.mean()) / theta.std()
    return -theta if theta[esquerda].mean() > theta[direita].mean() else theta


def _alinhar_e_padronizar(theta, alpha, beta, esquerda, direita):
    """Por cadeia: inverte o sinal se esquerda > direita. Por amostra: padroniza theta e
    ajusta alpha/beta para que o preditor linear não mude."""
    sinal = np.where(
        theta[..., esquerda].mean(axis=(1, 2)) > theta[..., direita].mean(axis=(1, 2)), -1.0, 1.0
    )[:, None, None]
    theta, beta = theta * sinal, beta * sinal
    media = theta.mean(axis=-1, keepdims=True)
    desvio = theta.std(axis=-1, keepdims=True)
    # beta*theta - alpha = (beta*desvio)*theta_pad - (alpha - beta*media)
    return (theta - media) / desvio, alpha - beta * media, beta * desvio


def estimar(
    m: MatrizVotos,
    esquerda: np.ndarray,
    direita: np.ndarray,
    aquecimento: int = 1000,
    amostras: int = 1000,
    cadeias: int = 2,
    semente: int = 20231,
) -> Resultado:
    n_dep, n_vot = m.forma
    inicio = valor_inicial(m, esquerda, direita)
    kernel = NUTS(modelo, init_strategy=init_to_value(values={"theta": jnp.asarray(inicio)}))
    mcmc = MCMC(
        kernel,
        num_warmup=aquecimento,
        num_samples=amostras,
        num_chains=cadeias,
        chain_method="sequential",
        progress_bar=False,
    )
    mcmc.run(
        jax.random.PRNGKey(semente),
        jnp.asarray(m.i_dep),
        jnp.asarray(m.i_vot),
        n_dep,
        n_vot,
        y=jnp.asarray(m.y, dtype=jnp.float32),
        extra_fields=("diverging",),
    )
    s = {k: np.asarray(v) for k, v in mcmc.get_samples(group_by_chain=True).items()}
    theta, alpha, beta = _alinhar_e_padronizar(s["theta"], s["alpha"], s["beta"], esquerda, direita)
    return Resultado(
        theta=theta.reshape(-1, n_dep),
        alpha=alpha.reshape(-1, n_vot),
        beta=beta.reshape(-1, n_vot),
        rhat_max=float(np.nanmax(split_gelman_rubin(theta))),
        ess_min=float(np.nanmin(effective_sample_size(theta))),
        divergencias=int(np.asarray(mcmc.get_extra_fields()["diverging"]).sum()),
    )
