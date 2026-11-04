from datetime import date

import httpx
import pytest

from polaritics.coleta import camara
from polaritics.coleta.camara import (
    ARQUIVOS_ANUAIS,
    ARQUIVOS_UNICOS,
    ColetorCamara,
    ErroColeta,
    anos_a_atualizar,
    checar_sanidade,
)

HOJE = date(2026, 11, 4)


def csv_com(colunas, linhas=()):
    cabecalho = ";".join(f'"{c}"' for c in sorted(colunas))
    return ("﻿" + "\n".join([cabecalho, *linhas]) + "\n").encode()


class ServidorFalso:
    """Responde aos arquivos da Câmara; anos em `ausentes` retornam 404."""

    def __init__(self, ausentes=(), falhas_transitorias=0):
        self.ausentes = set(ausentes)
        self.falhas_restantes = falhas_transitorias
        self.pedidos = []
        self.versao = "v1"

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.pedidos.append(request.url.path)
        if self.falhas_restantes:
            self.falhas_restantes -= 1
            return httpx.Response(503)
        arquivo = request.url.path.rsplit("/", 1)[-1].removesuffix(".csv")
        nome, _, ano = arquivo.partition("-")
        if ano and int(ano) in self.ausentes:
            return httpx.Response(404)
        colunas = ARQUIVOS_ANUAIS.get(nome) or ARQUIVOS_UNICOS[nome]
        return httpx.Response(200, content=csv_com(colunas, [f'"{self.versao}"']))


def coletor(tmp_path, servidor):
    return ColetorCamara(tmp_path, httpx.Client(transport=httpx.MockTransport(servidor)))


@pytest.fixture(autouse=True)
def sem_espera(monkeypatch):
    monkeypatch.setattr(camara.time, "sleep", lambda _: None)


def test_anos_a_atualizar_sem_forcar_so_corrente_e_anterior():
    assert anos_a_atualizar(57, HOJE, forcar=False) == [2025, 2026]
    assert anos_a_atualizar(57, HOJE, forcar=True) == [2023, 2024, 2025, 2026]
    assert anos_a_atualizar(57, date(2027, 1, 10), forcar=False) == [2026, 2027]


def test_primeira_coleta_baixa_todos_os_anos_iniciados(tmp_path):
    servidor = ServidorFalso()
    c = coletor(tmp_path, servidor)
    c.coletar(57, hoje=HOJE)
    esperados = len(ARQUIVOS_UNICOS) + 4 * len(ARQUIVOS_ANUAIS)
    assert len(servidor.pedidos) == esperados
    assert not any("2027" in p for p in servidor.pedidos)
    assert (tmp_path / "votacoes-2023.csv").exists()
    assert len(c.manifesto) == esperados
    assert not list(tmp_path.glob("*.parcial"))


def test_segunda_coleta_nao_rebaixa_anos_encerrados(tmp_path):
    coletor(tmp_path, ServidorFalso()).coletar(57, hoje=HOJE)
    servidor = ServidorFalso()
    coletor(tmp_path, servidor).coletar(57, hoje=HOJE)
    assert not any("2023" in p or "2024" in p for p in servidor.pedidos)
    assert any("2025" in p for p in servidor.pedidos)


def test_manifesto_registra_quando_o_conteudo_mudou(tmp_path):
    coletor(tmp_path, ServidorFalso()).coletar(57, hoje=HOJE)
    primeiro = ColetorCamara(tmp_path).manifesto["votacoes-2026.csv"]

    coletor(tmp_path, ServidorFalso()).coletar(57, hoje=HOJE)
    igual = ColetorCamara(tmp_path).manifesto["votacoes-2026.csv"]
    assert igual.sha256 == primeiro.sha256
    assert igual.alterado_em == primeiro.alterado_em

    servidor = ServidorFalso()
    servidor.versao = "v2"
    coletor(tmp_path, servidor).coletar(57, hoje=HOJE)
    mudou = ColetorCamara(tmp_path).manifesto["votacoes-2026.csv"]
    assert mudou.sha256 != primeiro.sha256


def test_ano_corrente_ainda_nao_publicado_e_ignorado(tmp_path):
    c = coletor(tmp_path, ServidorFalso(ausentes={2027}))
    c.coletar(57, hoje=date(2027, 1, 5))
    assert not (tmp_path / "votacoes-2027.csv").exists()
    assert (tmp_path / "votacoes-2026.csv").exists()


def test_ano_passado_ausente_e_erro(tmp_path):
    with pytest.raises(ErroColeta, match="não encontrado"):
        coletor(tmp_path, ServidorFalso(ausentes={2024})).coletar(57, hoje=HOJE)


def test_erro_transitorio_e_repetido(tmp_path):
    servidor = ServidorFalso(falhas_transitorias=2)
    reg = coletor(tmp_path, servidor).baixar("legislaturas", None, ARQUIVOS_UNICOS["legislaturas"])
    assert reg is not None
    assert len(servidor.pedidos) == 3


def test_colunas_ausentes_falham_e_nao_deixam_arquivo(tmp_path):
    with pytest.raises(ErroColeta, match="colunas ausentes"):
        coletor(tmp_path, ServidorFalso()).baixar("legislaturas", None, {"colunaInexistente"})
    assert not list(tmp_path.iterdir())


def test_checar_sanidade_exige_minimo_em_anos_completos(tmp_path):
    colunas = ARQUIVOS_ANUAIS["votacoes"]
    # colunas em ordem alfabética: data, descricao, id, siglaOrgao
    nominal = '"2025-01-01";"Aprovado. Sim: 300; Não: 100; Total: 400.";"x";"PLEN"'
    simbolica = '"2025-01-01";"Aprovado.";"y";"PLEN"'
    (tmp_path / "votacoes-2025.csv").write_bytes(csv_com(colunas, [nominal] * 200))
    (tmp_path / "votacoes-2026.csv").write_bytes(csv_com(colunas, [nominal] * 3))
    assert checar_sanidade(tmp_path, 57, HOJE) == {2025: 200, 2026: 3}

    (tmp_path / "votacoes-2025.csv").write_bytes(csv_com(colunas, [simbolica] * 200))
    with pytest.raises(ErroColeta, match="votações nominais"):
        checar_sanidade(tmp_path, 57, HOJE)
