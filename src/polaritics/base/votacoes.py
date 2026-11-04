"""Regras de classificação de votações e de codificação de votos (metodologia, seção 3)."""

import re

MERITO = "merito"
PROCEDIMENTO = "procedimento"
ELEICAO = "eleicao"
INDEFINIDO = "indefinido"

# Resultado + (opcional) qualificador entre vírgulas + artigo + objeto votado.
# Ex.: "Aprovada, em primeiro turno, a Proposta de Emenda à Constituição nº 18 ..."
_RESULTADO = re.compile(
    r"^(?:aprovad|rejeitad|mantid|suprimid)[oa]s?\.?\s*(?:,(?P<qualificador>[^,]*),)?"
    r"\s*(?:(?:o|a|os|as)\s+)?(?P<objeto>.*)",
    re.IGNORECASE | re.DOTALL,
)
_OBJETOS_PROCEDIMENTO = re.compile(
    r"^(?:requerimento|recurso|prefer[êe]ncia|destaque|inclus[ãa]o|adiamento|retirada)",
    re.IGNORECASE,
)


def classificar_votacao(descricao: str) -> str:
    """Mérito (o conteúdo em si) ou procedimento (o andamento da pauta)."""
    texto = " ".join(descricao.split())
    if texto.lower().startswith("votos:"):
        return ELEICAO  # eleição de pessoas (ex.: ministro do TCU)
    if not (m := _RESULTADO.match(texto)):
        return INDEFINIDO
    if "apreciação preliminar" in (m["qualificador"] or "").lower():
        return PROCEDIMENTO  # admissibilidade de MP/PEC, não o conteúdo
    return PROCEDIMENTO if _OBJETOS_PROCEDIMENTO.match(m["objeto"]) else MERITO


def eh_nominal(descricao: str) -> bool:
    # Votações nominais trazem o placar ("Total: 458"); simbólicas, não.
    return "total:" in descricao.lower()


# Obstrução é posição política ativa: conta como "Não" (decisão D1).
CODIFICACAO_VOTO = {"Sim": 1, "Não": 0, "Obstrução": 0}


def codificar_voto(voto: str | None) -> int | None:
    """1 = Sim, 0 = Não/Obstrução, None = ausência, abstenção, art. 17 ou voto secreto."""
    return CODIFICACAO_VOTO.get(voto or "")
