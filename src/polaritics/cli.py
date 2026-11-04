"""Linha de comando: `uv run polaritics <comando>`."""

import argparse
import logging
from datetime import date

from polaritics.base.carga import construir_base
from polaritics.coleta.camara import ColetorCamara, checar_sanidade
from polaritics.config import LEGISLATURAS


def coletar(args: argparse.Namespace) -> None:
    hoje = date.today()
    coletor = ColetorCamara()
    coletor.coletar(args.legislatura, hoje=hoje, forcar=args.forcar)
    contagem = checar_sanidade(coletor.destino, args.legislatura, hoje)
    for ano, n in contagem.items():
        print(f"{ano}: {n} votações nominais de plenário")


def base(_args: argparse.Namespace) -> None:
    print(f"base construída em {construir_base()}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="polaritics")
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("coletar", help="baixa os arquivos em lote da Câmara")
    p.add_argument("--legislatura", type=int, choices=sorted(LEGISLATURAS), default=57)
    p.add_argument("--forcar", action="store_true", help="baixa de novo também anos encerrados")
    p.set_defaults(func=coletar)

    p = sub.add_parser("base", help="constrói a base DuckDB a partir dos dados brutos")
    p.set_defaults(func=base)

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args.func(args)


if __name__ == "__main__":
    main()
