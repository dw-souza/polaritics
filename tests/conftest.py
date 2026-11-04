"""Auxiliares para montar arquivos brutos falsos da Câmara nos testes."""

import csv


def escrever(caminho, linhas):
    with caminho.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]), delimiter=";", quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(linhas)


def deputado(id_, nome=None, legislatura_final="57", cpf="", nascimento=""):
    return {
        "uri": f"https://x/deputados/{id_}",
        "nome": nome or f"Dep {id_}",
        "idLegislaturaFinal": legislatura_final,
        "nomeCivil": "",
        "cpf": cpf,
        "siglaSexo": "",
        "dataNascimento": nascimento,
    }


def votacao(id_, data, descricao, orgao="PLEN"):
    return {
        "id": id_,
        "data": data,
        "dataHoraRegistro": f"{data}T18:00:00",
        "siglaOrgao": orgao,
        "descricao": descricao,
    }


def voto(id_votacao, dep, data_hora, voto_, partido):
    return {
        "idVotacao": id_votacao,
        "dataHoraVoto": data_hora,
        "voto": voto_,
        "deputado_id": dep,
        "deputado_siglaPartido": partido,
        "deputado_siglaUf": "SP",
    }


def orientacao(id_votacao, bancada, orientacao_):
    return {"idVotacao": id_votacao, "siglaBancada": bancada, "orientacao": orientacao_}


def escrever_brutos(diretorio, deputados, votacoes, votos, orientacoes, ano=2024):
    diretorio.mkdir(parents=True, exist_ok=True)
    escrever(diretorio / "deputados.csv", deputados)
    escrever(diretorio / f"votacoes-{ano}.csv", votacoes)
    escrever(diretorio / f"votacoesVotos-{ano}.csv", votos)
    escrever(diretorio / f"votacoesOrientacoes-{ano}.csv", orientacoes)
    return diretorio
