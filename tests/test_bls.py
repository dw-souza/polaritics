from polaritics.coleta import bls


def escrever_tab(caminho, linhas):
    colunas = ["wave", *bls.COLUNAS]
    texto = ["\t".join(colunas)]
    for linha in linhas:
        texto.append("\t".join(str(linha.get(c, -999)) for c in colunas))
    caminho.write_text("\n".join(texto) + "\n", encoding="utf-8")


def test_notas_media_da_onda_2021_ignora_ausentes_e_poucas_respostas(tmp_path):
    arquivo = tmp_path / "bls.tab"
    linhas = [{"wave": "2021", "lrpt": 2, "lrpl": 8, "lrdem": 7, "lrpsl": 9} for _ in range(10)]
    linhas += [{"wave": "2021", "lrpt": -999, "lrrede": 5}]  # ausência e partido com 1 resposta
    linhas += [{"wave": "2017", "lrpt": 9} for _ in range(10)]  # outra onda
    escrever_tab(arquivo, linhas)
    notas = bls.notas(arquivo, verificar_hash=False)
    assert notas["PT"] == 2
    assert notas["PL"] == 8
    assert "REDE" not in notas
    assert notas["UNIÃO"] == 8  # fusão DEM + PSL
    assert "PRD" not in notas  # falta o Patriota


def test_resumo_exportado_e_lido_sem_o_arquivo_bruto(tmp_path):
    bruto = tmp_path / "bls.tab"
    escrever_tab(bruto, [{"wave": "2021", "lrpt": 2, "lrpl": 8} for _ in range(10)])
    resumo = tmp_path / "resumo.csv"
    bls.exportar_resumo(resumo, bruto, verificar_hash=False)
    assert resumo.read_text(encoding="utf-8").startswith("# Power")
    lido = bls.notas(tmp_path / "inexistente.tab", resumo=resumo)
    assert lido == {"PT": 2.0, "PL": 8.0}
