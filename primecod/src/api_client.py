"""Cliente HTTP para acessar a API Primecod.

Responsavel por fazer paginacao atraves de todas as paginas de produtos
e salvar o resultado em JSON.
"""

from __future__ import annotations

import json
from typing import Any

import requests

from . import config


def _get_headers() -> dict[str, str]:
    """Retorna os headers necessarios para a autenticacao na API."""
    return {
        "Authorization": f"{config.PRIMECOD_API_TOKEN_TYPE} {config.PRIMECOD_API_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _fetch_page(page: int) -> dict[str, Any]:
    """Busca uma pagina de produtos da API.
    
    Args:
        page: Numero da pagina (comeca em 1)
    
    Returns:
        Dicionario com a resposta da API
    
    Raises:
        requests.RequestException: Se houver erro na requisicao
    """
    # Construir URL com query string
    url = f"{config.PRIMECOD_API_URL}?page={page}&per_page={config.PRIMECOD_PAGE_SIZE}&country_code={config.PRIMECOD_COUNTRY_CODE}"
    
    headers = _get_headers()
    
    print(f"  [api] Buscando pagina {page}...")
    
    # Tentar POST primeiro (algumas APIs exigem)
    response = requests.post(
        url,
        headers=headers,
        timeout=30,
    )
    
    # Se POST falhar com 405, tentar GET
    if response.status_code == 405:
        print(f"  [api] POST retornou 405, tentando GET...")
        response = requests.get(
            url,
            headers=headers,
            timeout=30,
        )
    
    response.raise_for_status()
    return response.json()


def run_capture() -> int:
    """Busca todos os produtos da API Primecod com paginacao.
    
    Retorna:
        Total de produtos capturados
    """
    print("[1/4] Capturando produtos da API Primecod...")
    
    all_products = []
    total_pages = None
    current_page = 1
    
    try:
        while True:
            data = _fetch_page(current_page)
            
            # Na primeira pagina, descobrimos o total de paginas
            if total_pages is None:
                total_pages = data.get("last_page", 1)
                print(f"  [api] Total de paginas: {total_pages}")
            
            # Extrai os produtos desta pagina
            page_products = data.get("data", [])
            all_products.extend(page_products)
            
            print(f"  [api] Pagina {current_page}/{total_pages}: {len(page_products)} produto(s)")
            
            # Se chegamos na ultima pagina, para
            if current_page >= total_pages:
                break
            
            current_page += 1
    
    except requests.RequestException as exc:
        raise RuntimeError(f"Erro ao acessar API Primecod: {exc}") from exc
    
    # Salva o JSON bruto
    config.PRODUCTS_RAW_JSON.parent.mkdir(parents=True, exist_ok=True)
    config.PRODUCTS_RAW_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    
    # Salva a lista de produtos
    config.PRODUCTS_JSON.write_text(
        json.dumps(all_products, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    
    print(f"OK! {len(all_products)} produto(s) capturado(s)")
    print(f"  Salvos em: {config.PRODUCTS_JSON}")
    
    return len(all_products)


if __name__ == "__main__":
    run_capture()
