"""Orquestrador do projeto integration (catalogo unificado -> Shopify).

Uso:
    python main.py all                        # sincroniza as duas integracoes e abre a web (padrao)
    python main.py sync <ecomhub|primecod>   # compara SKUs do catalogo com a Shopify
    python main.py sync-all                   # sincroniza as duas integracoes
    python main.py send <ecomhub|primecod> SKU [SKU ...]   # envia SKUs especificos
    python main.py web                        # abre a interface web (marcar e enviar)

Pre-requisitos:
    - A tabela unificada (unified_catalog.products) ja populada pelo unify_catalog.py.
    - .env preenchido (copie de .env.example). Sem credenciais Shopify, o `sync`
      ainda roda e marca tudo como "nao cadastrado".
"""

from __future__ import annotations

import sys

from src import compare, config
from src.sender import send_skus


def _check_integration(name: str) -> str:
    if name not in config.INTEGRATIONS:
        print(f"Integracao invalida: {name!r}. Use uma de {config.INTEGRATIONS}.")
        sys.exit(1)
    return name


def main() -> None:
    args = sys.argv[1:]
    cmd = args[0] if args else "all"

    if cmd == "all":
        for integ in config.INTEGRATIONS:
            compare.run_sync(integ)
        from src.web import run

        print(f"\nServidor em http://127.0.0.1:{config.PORT}")
        run()

    elif cmd == "sync":
        if len(args) < 2:
            print("Uso: python main.py sync <ecomhub|primecod>")
            sys.exit(1)
        compare.run_sync(_check_integration(args[1]))

    elif cmd == "sync-all":
        for integ in config.INTEGRATIONS:
            compare.run_sync(integ)

    elif cmd == "send":
        if len(args) < 3:
            print("Uso: python main.py send <ecomhub|primecod> SKU [SKU ...]")
            sys.exit(1)
        integ = _check_integration(args[1])
        res = send_skus(integ, args[2:])
        print(
            f"Criados: {len(res['created'])}; ignorados: {len(res['skipped'])}; "
            f"erros: {len(res['errors'])}"
        )
        for e in res["errors"]:
            print(f"  [erro] {e['sku']}: {e['error']}")

    elif cmd == "web":
        from src.web import run

        print(f"Servidor em http://127.0.0.1:{config.PORT}")
        run()

    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
