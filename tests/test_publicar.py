import pytest

from polaritics.publicar import neon


def test_url_banco_le_env_ignorando_comentario(tmp_path, monkeypatch):
    monkeypatch.delenv(neon.VARIAVEL_URL, raising=False)
    env = tmp_path / ".env"
    env.write_text(
        f"OUTRA=1\n{neon.VARIAVEL_URL}=postgresql://u:p@host/db?sslmode=require   # unpooled\n",
        encoding="utf-8",
    )
    assert neon.url_banco(env) == "postgresql://u:p@host/db?sslmode=require"


def test_url_banco_prefere_variavel_de_ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv(neon.VARIAVEL_URL, "postgresql://ambiente")
    assert neon.url_banco(tmp_path / "inexistente") == "postgresql://ambiente"


def test_url_banco_sem_configuracao_falha(tmp_path, monkeypatch):
    monkeypatch.delenv(neon.VARIAVEL_URL, raising=False)
    with pytest.raises(neon.ErroPublicacao):
        neon.url_banco(tmp_path / "inexistente")


def test_comandos_separa_e_remove_comentarios():
    sql = (
        "-- cabeçalho; com ponto e vírgula\ncreate schema x;\n\ncreate table x.t (a int); -- fim\n"
    )
    assert neon._comandos(sql) == ["create schema x", "create table x.t (a int)"]


def test_esquema_pg_tem_todas_as_tabelas_publicadas():
    comandos = neon._comandos(neon.ESQUEMA_PG.read_text(encoding="utf-8"))
    criadas = {c.split("publicado.")[1].split()[0] for c in comandos if "create table" in c}
    assert set(neon.TABELAS_POR_LEGISLATURA) <= criadas
    assert {"publicacao", "partido", "deputado"} <= criadas
