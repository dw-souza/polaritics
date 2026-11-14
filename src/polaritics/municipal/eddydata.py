"""Portal da Transparência de Franca (sistema EddyData): despesas de viagem e folha da Câmara.

O portal público (https://eddydata.franca.sp.gov.br/010000/transparencia/) consulta uma API com
um token anônimo, e a coleta reproduz o que o navegador faz:

1. ``POST usuarios/token-publico`` devolve um JWT de 30 minutos com ``iat``, ``id`` e ``chave``;
2. cada requisição leva ``Authorization: JWT <token>``, ``agora`` (epoch em ms) e
   ``codigo = bcrypt(((agora - iat) / id).toFixed(0), sal=chave)``. O token público tem
   ``id = 0``, então o texto assinado é ``"Infinity"``, como no navegador.

O mapeamento do acesso anônimo veio do projeto franca-transparencia, do mesmo mantenedor; o
código aqui é próprio. O servidor não envia o certificado intermediário da Certum: ele vai
junto do pacote (baixado de certumdvtlsg2r39ca.repository.certum.pl, SHA-256
83:C0:A5:A7:…:04:40:83) e é somado às raízes do certifi. A verificação TLS nunca é desligada.

Só uma lista branca de campos é gravada: o favorecido de um empenho traz dados pessoais e
bancários, que não interessam aqui.
"""

import base64
import json
import logging
import math
import ssl
import time
from datetime import UTC, datetime
from pathlib import Path

import bcrypt
import certifi
import httpx

from polaritics.municipal.siscam import gravar_com_manifesto

log = logging.getLogger(__name__)

API = "https://eddydata-api.franca.sp.gov.br/api/v1/franca"
CIDADE = 1
INTERMEDIARIO = Path(__file__).with_name("certum_dv_tls_g2_r39_ca.pem")
MARGEM_TOKEN_S = 120
PAUSA_S = 0.5
POR_PAGINA = 500
TENTATIVAS = 4
# Elementos de despesa de viagem (o próprio portal chama 339033% de "despesas de viagens"):
# 3.3.90.14 diárias e 3.3.90.33 passagens e locomoção.
DESPESAS_VIAGEM = ("339014%", "339033%")
CARGO_ASSESSOR = "ASSESSOR(A) PARLAMENTAR"
ANO_INICIAL = 2021


class ErroEddyData(RuntimeError):
    pass


def contexto_tls() -> ssl.SSLContext:
    contexto = ssl.create_default_context(cafile=certifi.where())
    contexto.load_verify_locations(cafile=str(INTERMEDIARIO))
    return contexto


def js_to_fixed0(numerador: int, divisor: int) -> str:
    """``(numerador / divisor).toFixed(0)`` com a semântica do JavaScript (Infinity, NaN)."""
    if divisor == 0:
        return "NaN" if numerador == 0 else ("Infinity" if numerador > 0 else "-Infinity")
    x = numerador / divisor
    n = math.floor(abs(x) + 0.5)
    return f"-{n}" if x < 0 else str(n)


def _claims(token: str) -> dict:
    corpo = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(corpo + "=" * (-len(corpo) % 4)))


class ClienteEddyData:
    def __init__(self, cliente: httpx.Client | None = None, relogio=time.time):
        self.cliente = cliente or httpx.Client(timeout=120, verify=contexto_tls())
        self.relogio = relogio
        self._token: str | None = None
        self._claims: dict = {}

    def _autenticar(self) -> None:
        resposta = self.cliente.post(
            f"{API}/usuarios/token-publico", headers={"Content-Type": "application/json"}
        )
        resposta.raise_for_status()
        token = resposta.json().get("token")
        if not isinstance(token, str) or token.count(".") != 2:
            raise ErroEddyData("token-publico não devolveu um JWT")
        self._token, self._claims = token, _claims(token)

    def cabecalhos(self) -> dict[str, str]:
        exp = self._claims.get("exp")
        if not self._token or (exp is not None and self.relogio() > float(exp) - MARGEM_TOKEN_S):
            self._autenticar()
        agora = int(self.relogio() * 1000)
        texto = js_to_fixed0(agora - int(self._claims["iat"]), int(self._claims["id"]))
        codigo = bcrypt.hashpw(texto.encode(), str(self._claims["chave"]).encode()).decode()
        return {
            "Authorization": f"JWT {self._token}",
            "Content-Type": "application/json",
            "agora": str(agora),
            "codigo": codigo,
        }

    def get(self, caminho: str, params: dict) -> dict:
        for tentativa in range(1, TENTATIVAS + 1):
            time.sleep(PAUSA_S)
            try:
                resposta = self.cliente.get(
                    f"{API}/{CIDADE}/{caminho}", params=params, headers=self.cabecalhos()
                )
                if resposta.status_code == 401 and tentativa == 1:
                    self._token = None  # token revogado no servidor: renova uma vez
                    continue
                resposta.raise_for_status()
                if "json" not in resposta.headers.get("content-type", ""):
                    raise ErroEddyData(f"{caminho} não devolveu JSON")
                return resposta.json()
            except (httpx.TransportError, httpx.HTTPStatusError) as erro:
                if tentativa == TENTATIVAS:
                    raise ErroEddyData(f"falha em {caminho}: {erro}") from erro
                time.sleep(2.0 * 2 ** (tentativa - 1))
        raise AssertionError("inalcançável")

    def paginar(self, recurso: str, params: dict, por_pagina: int = POR_PAGINA) -> list[dict]:
        registros, pagina = [], 1
        while True:
            dados = self.get(f"{recurso}/{pagina}/{por_pagina}", params)
            registros += dados.get("content") or []
            if pagina >= int(dados.get("totalPages") or 0):
                break
            pagina += 1
        total = int(dados.get("numberOfElements") or 0)
        if len(registros) != total:
            raise ErroEddyData(f"{recurso}: {len(registros)} registros, o portal informa {total}")
        return registros

    def orgao_id(self, codigo: str) -> int:
        conteudo = self.get("orgaos/filtrar", {"codigo": codigo, "cidade.id": CIDADE})["content"]
        if not conteudo:
            raise ErroEddyData(f"órgão {codigo} não encontrado no EddyData")
        return int(conteudo[0]["id"])


def _empenho(r: dict) -> dict:
    despesa = (r.get("ficha") or {}).get("despesa") or {}
    return {
        "id": r["id"],
        "numero": r.get("numero"),
        "data": (r.get("data_empenho") or "")[:10],
        "especie": r.get("especie"),  # EMO = empenho; EOA = anulação (mesmo número, valor < 0)
        "valor": float(r.get("valor_empenho") or 0),
        "despesa": despesa.get("codigo"),
        "subelemento": (r.get("subelemento") or {}).get("nome"),
        "historico": r.get("historico"),
    }


def _holerite(r: dict, ano: int, mes: int) -> dict:
    funcionario = r.get("funcionario") or {}
    return {
        "ano": ano,
        "mes": mes,
        "nome": (funcionario.get("pessoa") or {}).get("nome"),
        "cargo": (funcionario.get("cargo") or {}).get("nome"),
        "calculo": r.get("calculo"),
        "valor_bruto": float(r.get("valor_bruto") or 0),
    }


def coletar(codigo_orgao: str, destino: Path, cliente: ClienteEddyData | None = None) -> dict:
    """Empenhos de viagem e folha (só vereadores e assessores) da Câmara, de 2021 em diante."""
    cliente = cliente or ClienteEddyData()
    orgao = cliente.orgao_id(codigo_orgao)
    hoje = datetime.now(UTC).date()
    empenhos, folha = [], []
    for ano in range(ANO_INICIAL, hoje.year + 1):
        for despesa in DESPESAS_VIAGEM:
            empenhos += [
                _empenho(r)
                for r in cliente.paginar(
                    "empenhos",
                    {
                        "ignoreCondObrig": "true",
                        "orgao.id": orgao,
                        "data_empenho$ge": f"{ano}-01-01",
                        "data_empenho$le": f"{ano}-12-31",
                        "ficha.despesa.codigo$like": despesa,
                        "relations": "ficha,ficha.despesa,subelemento",
                    },
                )
            ]
        for mes in range(1, 13 if ano < hoje.year else hoje.month + 1):
            folha += [
                _holerite(r, ano, mes)
                for r in cliente.paginar(
                    "holerites",
                    {
                        "ignoreCondObrig": "true",
                        "orgao.id": orgao,
                        "referencia.ano": ano,
                        "referencia.mes": mes,
                        "relations": "funcionario,funcionario.pessoa,funcionario.cargo",
                        "orderBy": "id$ASC",
                    },
                )
                if ((r.get("funcionario") or {}).get("cargo") or {}).get("nome")
                in (CARGO_ASSESSOR, "VEREADOR", "PRESIDENTE")
            ]
        log.info("eddydata %d: %d empenhos de viagem, %d holerites", ano, len(empenhos), len(folha))
    gravar_com_manifesto(destino, "eddydata_viagens.json", f"{API}/{CIDADE}/empenhos", empenhos)
    gravar_com_manifesto(destino, "eddydata_folha.json", f"{API}/{CIDADE}/holerites", folha)
    return {"empenhos": len(empenhos), "holerites": len(folha)}
