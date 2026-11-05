import duckdb
import pytest
from conftest import deputado, escrever_brutos, orientacao, votacao, voto

from polaritics.base.carga import construir_base
from polaritics.base.conexao import conectar
from polaritics.medidas.ideologia.calculo import impressao, preparar
from polaritics.publicar import neon

PARTIDO = {"1": "PT", "2": "PT", "3": "PT", "4": "PL", "5": "PL", "6": "PL"}


def especialistas(caminho):
    linhas = ["id;ideol_22_pt;ideol_22_pl"] + [f"{i};{2 + i % 2};{9 - i % 2}" for i in range(4)]
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return caminho


def montar(tmp_path, voto_do_1_na_b="Sim"):
    """Base pequena com 2 votações divididas (PT × PL); o voto do deputado 1 em 'b' varia."""
    votos = {
        "a": ["Sim"] * 3 + ["Não"] * 3,
        "b": [voto_do_1_na_b, "Sim", "Sim", "Não", "Não", "Não"],
    }
    brutos = escrever_brutos(
        tmp_path / "raw",
        deputados=[deputado(d) for d in PARTIDO],
        votacoes=[
            votacao("a", "2024-03-01", "Aprovado o Projeto de Lei nº 1. Sim: 3; Não: 3; Total: 6."),
            votacao("b", "2024-03-02", "Aprovado o Projeto de Lei nº 2. Sim: 3; Não: 3; Total: 6."),
        ],
        votos=[
            voto(v, dep, f"2024-03-0{1 if v == 'a' else 2}T18:00:00", vs[i], PARTIDO[dep])
            for v, vs in votos.items()
            for i, dep in enumerate(PARTIDO)
        ],
        orientacoes=[orientacao("a", "Governo", "Sim")],
    )
    return construir_base(
        brutos,
        tmp_path / "base.duckdb",
        arquivo_especialistas=especialistas(tmp_path / "experts.csv"),
    )


def test_reconstruir_a_base_nao_apaga_o_modelo(tmp_path):
    base = montar(tmp_path)
    modelo = tmp_path / "modelo.duckdb"
    with conectar(base, modelo) as con:
        con.execute("create table modelo.ideologia (id_camara varchar)")
        con.execute("insert into modelo.ideologia values ('1')")
    montar(tmp_path)  # recria a base do zero
    with conectar(base, modelo, somente_leitura=True) as con:
        # a tabela do modelo aparece sem prefixo, ao lado das tabelas da base
        assert con.execute("select count(*) from ideologia").fetchall() == [(1,)]
        assert con.execute("select count(*) from voto").fetchall()[0][0] == 12


def test_impressao_muda_so_quando_os_votos_mudam(tmp_path):
    def calcular(caminho, voto_b):
        base = montar(caminho, voto_b)
        with duckdb.connect(str(base), read_only=True) as con:
            return impressao(*preparar(con, 57, "todas"))

    igual_1 = calcular(tmp_path / "x", "Sim")
    igual_2 = calcular(tmp_path / "y", "Sim")
    diferente = calcular(tmp_path / "z", "Não")
    assert igual_1 == igual_2
    assert igual_1 != diferente


def test_publicacao_recusa_modelo_calculado_com_outros_votos(tmp_path):
    base = montar(tmp_path, "Não")
    with duckdb.connect(str(base), read_only=True) as con:
        antiga = impressao(*preparar(con, 57, "todas"))
    montar(tmp_path, "Sim")  # a base muda depois do cálculo do modelo
    modelo = tmp_path / "modelo.duckdb"
    with conectar(base, modelo) as con:
        con.execute(
            "create table modelo.ideologia_diagnostico (legislatura integer, variante varchar, "
            "impressao varchar)"
        )
        con.execute("insert into modelo.ideologia_diagnostico values (57, 'todas', ?)", [antiga])
        with pytest.raises(neon.ErroPublicacao, match="mudaram"):
            neon.conferir_impressao(con, 57, ["todas"])
        con.execute(
            "update modelo.ideologia_diagnostico set impressao = ?",
            [impressao(*preparar(con, 57, "todas"))],
        )
        neon.conferir_impressao(con, 57, ["todas"])  # com a impressão atual, passa
