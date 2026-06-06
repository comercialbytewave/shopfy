"""Robo de captura do EcomHub.

Faz login no portal (https://go.ecomhub.app/login), navega ate a guia
Produtos e captura a resposta JSON da API que comeca com
https://api.ecomhub.app/api/productsWorkspaces.

A captura e feita interceptando o trafego de rede do navegador, entao
pegamos exatamente o mesmo JSON que o portal recebe da API.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from playwright.async_api import Page, Response, TimeoutError as PWTimeout, async_playwright

from . import config


async def _save_debug(page: Page, label: str) -> None:
    """Salva screenshot + HTML para ajudar a depurar falhas de login/captura."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        await page.screenshot(path=str(config.DEBUG_DIR / f"{label}_{ts}.png"), full_page=True)
        html = await page.content()
        (config.DEBUG_DIR / f"{label}_{ts}.html").write_text(html, encoding="utf-8")
        print(f"  [debug] capturas salvas em {config.DEBUG_DIR} (prefixo {label}_{ts})")
    except Exception as exc:  # pragma: no cover - best effort
        print(f"  [debug] nao foi possivel salvar debug: {exc}")


async def _fill_first(page: Page, selectors: list[str], value: str, what: str) -> bool:
    """Tenta preencher o primeiro seletor que existir na pagina."""
    for sel in selectors:
        loc = page.locator(sel).first
        try:
            if await loc.count() > 0 and await loc.is_visible():
                await loc.fill(value)
                print(f"  [login] {what} preenchido via seletor: {sel}")
                return True
        except Exception:
            continue
    return False


async def _do_login(page: Page) -> None:
    """Preenche o formulario de login com heuristicas robustas de seletor."""
    email, password = config.require_credentials()
    print(f"[1/3] Abrindo pagina de login: {config.LOGIN_URL}")
    await page.goto(config.LOGIN_URL, wait_until="networkidle")

    # Aguarda o formulario renderizar (SPA)
    try:
        await page.wait_for_selector("input", timeout=20000)
    except PWTimeout:
        await _save_debug(page, "login_sem_inputs")
        raise RuntimeError("Nenhum campo de input apareceu na pagina de login.")

    email_ok = await _fill_first(
        page,
        [
            "#input-email",
            "input[type='email']",
            "input[name='email']",
            "input[id='email']",
            "input[name*='email' i]",
            "input[placeholder*='mail' i]",
            "input[type='text']",
            "input:not([type='password']):not([type='hidden'])",
        ],
        email,
        "E-mail/usuario",
    )
    if not email_ok:
        await _save_debug(page, "login_sem_email")
        raise RuntimeError("Nao foi possivel localizar o campo de e-mail/usuario.")

    pass_ok = await _fill_first(
        page,
        [
            "#input-password",
            "input[type='password']",
            "input[name='password']",
            "input[id='password']",
            "input[name*='senha' i]",
            "input[placeholder*='senha' i]",
            "input[placeholder*='password' i]",
        ],
        password,
        "Senha",
    )
    if not pass_ok:
        await _save_debug(page, "login_sem_senha")
        raise RuntimeError("Nao foi possivel localizar o campo de senha.")

    # Escuta a resposta da API de autenticacao para saber o resultado real
    # do login (200 = ok, 4xx = credenciais/captcha rejeitados).
    auth_result: dict[str, Any] = {}

    async def on_auth(response: Response) -> None:
        if re.search(r"/(usersAuth/auth|auth|login|signin)\b", urlparse(response.url).path, re.I):
            if "auth_result" not in auth_result or response.status >= 400:
                auth_result["status"] = response.status
                auth_result["url"] = response.url

    page.on("response", on_auth)

    # Submete o formulario. Preferimos o botao por papel/texto (mais robusto).
    submitted = False
    try:
        btn = page.get_by_role("button", name=re.compile(r"entrar|login|acessar", re.I))
        if await btn.count() > 0:
            print("  [login] clicando em 'Entrar' (botao por texto/role)")
            await btn.first.click()
            submitted = True
    except Exception:
        pass

    if not submitted:
        for sel in [
            "button[type='submit']",
            "input[type='submit']",
            "button",
        ]:
            loc = page.locator(sel).first
            try:
                if await loc.count() > 0 and await loc.is_visible():
                    print(f"  [login] clicando em submit via seletor: {sel}")
                    await loc.click()
                    submitted = True
                    break
            except Exception:
                continue

    if not submitted:
        await page.keyboard.press("Enter")  # ultimo recurso

    # Sucesso = sair do path /login. ATENCAO: a URL de destino contem
    # "origin=login" na query, entao verificamos apenas o PATH, nunca a URL inteira.
    def left_login() -> bool:
        return "login" not in urlparse(page.url).path.lower()

    deadline = 30.0
    waited = 0.0
    while waited < deadline:
        await page.wait_for_timeout(500)
        waited += 0.5
        # Credenciais/captcha rejeitados pela API
        if auth_result.get("status", 0) >= 400:
            await _save_debug(page, "login_rejeitado")
            raise RuntimeError(
                f"Login rejeitado pela API (HTTP {auth_result['status']}). "
                f"Verifique ECOMHUB_EMAIL/ECOMHUB_PASSWORD no .env. "
                f"Veja tambem ./debug."
            )
        if left_login():
            break

    page.remove_listener("response", on_auth)

    if not left_login():
        await _save_debug(page, "login_falhou")
        raise RuntimeError(
            "Login nao concluiu (ainda no /login apos 30s). "
            "Pode ser captcha/credenciais. Veja os arquivos em ./debug."
        )

    print(f"  [login] login realizado com sucesso. URL atual: {page.url}")


def _set_offset(url: str, offset: int) -> str:
    """Devolve a mesma URL com o parametro de query `offset` alterado."""
    parts = urlparse(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["offset"] = str(offset)
    return urlunparse(parts._replace(query=urlencode(query)))


def _record_id(rec: dict[str, Any]) -> Any:
    """Chave usada para deduplicar registros entre paginas."""
    if "id" in rec:
        return ("id", rec["id"])
    return ("hash", json.dumps(rec, sort_keys=True, ensure_ascii=False))


def _auth_headers(headers: dict[str, str]) -> dict[str, str]:
    """Filtra os headers da requisicao original, mantendo os de autenticacao."""
    keep = {"authorization", "accept", "referer", "cookie", "user-agent"}
    out: dict[str, str] = {}
    for name, value in headers.items():
        low = name.lower()
        if low in keep or low.startswith("x-"):
            out[name] = value
    return out


# Limite de seguranca para nunca entrar em loop infinito de paginacao.
MAX_PAGES = 1000


async def _enrich_descriptions(
    context: Any, records: list[dict[str, Any]], headers: dict[str, str]
) -> int:
    """Preenche `description` de cada produto via {PRODUCT_API}/{id}.

    A lista de productsWorkspaces nao traz a descricao; ela so existe no
    endpoint de detalhe do produto. Busca em paralelo (com limite) reutilizando
    a mesma sessao autenticada. Produtos cuja chamada falhar ficam sem alterar.
    """
    sem = asyncio.Semaphore(max(1, config.DETAIL_CONCURRENCY))
    filled = 0

    async def one(rec: dict[str, Any]) -> None:
        nonlocal filled
        pid = rec.get("id")
        if not pid:
            return
        async with sem:
            try:
                resp = await context.request.get(
                    f"{config.PRODUCT_API}/{pid}", headers=headers, timeout=30000
                )
                if resp.status >= 400:
                    return
                body = await resp.json()
            except Exception:
                return
        if isinstance(body, dict):
            desc = body.get("description")
            if desc is not None and str(desc).strip():
                rec["description"] = desc
                filled += 1

    await asyncio.gather(*(one(r) for r in records))
    return filled


async def capture() -> dict[str, Any]:
    """Executa o fluxo completo, pagina via `offset` e retorna todos os registros."""
    # O endpoint /api/products responde de VARIAS formas na mesma pagina:
    #   - metadados (definicao das colunas, sem registros) -> ignoramos
    #   - widgets/atalhos com poucos registros e poucos campos (ex.: 2 itens
    #     com createdAt/id/isActive/name) -> NAO sao a lista de produtos
    #   - a lista real de produtos (48 por pagina, registros "ricos")
    # Por causa disso, em vez de pegar a 1a resposta, coletamos todas as
    # candidatas com registros e, no fim, escolhemos a melhor (mais registros,
    # desempatando pela que tem registros com mais campos).
    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    capture_event = asyncio.Event()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=config.HEADLESS)
        context = await browser.new_context()
        page = await context.new_page()

        async def on_response(response: Response) -> None:
            if response.url.startswith(config.API_PREFIX) and response.request.method == "GET":
                if response.url in seen_urls:
                    return
                try:
                    body = await response.json()
                except Exception:
                    return
                recs = extract_records(body)
                if not recs:
                    return  # metadados / resposta sem registros
                seen_urls.add(response.url)
                candidates.append(
                    {
                        "url": response.url,
                        "status": response.status,
                        "body": body,
                        "records": recs,
                        "headers": _auth_headers(await response.request.all_headers()),
                    }
                )
                print(
                    f"  [captura] candidato ({response.status}) - {len(recs)} "
                    f"registro(s) <- {urlparse(response.url).path}"
                )
                capture_event.set()

        page.on("response", on_response)

        try:
            await _do_login(page)

            print(f"[2/3] Navegando ate a guia Produtos: {config.PRODUCTS_URL}")
            # Tenta clicar num link/menu "Produtos"; se nao houver, navega direto.
            clicked = False
            for sel in [
                "a:has-text('Produtos')",
                "nav >> text=Produtos",
                "[href*='products']",
                "text=Produtos",
            ]:
                loc = page.locator(sel).first
                try:
                    if await loc.count() > 0 and await loc.is_visible():
                        await loc.click()
                        clicked = True
                        print(f"  [nav] clicou em Produtos via: {sel}")
                        break
                except Exception:
                    continue
            if not clicked:
                await page.goto(config.PRODUCTS_URL, wait_until="networkidle")

            print("[3/3] Aguardando a chamada da API de produtos...")
            try:
                await asyncio.wait_for(capture_event.wait(), timeout=30)
            except asyncio.TimeoutError:
                pass
            # Janela extra para coletar respostas concorrentes (a decoy e a lista
            # real chegam quase juntas) antes de escolher a melhor.
            await page.wait_for_timeout(3000)

            if not candidates:
                await _save_debug(page, "sem_captura")
                raise RuntimeError(
                    "Nao foi capturada nenhuma resposta com registros de "
                    f"{config.API_PREFIX}. Veja ./debug para investigar."
                )

            # Escolhe a resposta com mais registros (a lista real de produtos),
            # desempatando pela que tem registros com mais campos.
            def _richness(c: dict[str, Any]) -> tuple[int, int]:
                max_keys = max((len(r) for r in c["records"]), default=0)
                return (len(c["records"]), max_keys)

            captured = max(candidates, key=_richness)
            print(
                f"  [captura] escolhida resposta com {len(captured['records'])} "
                f"registro(s) <- {urlparse(captured['url']).path}"
            )

            # ---- Paginacao: percorre offset=1,2,3... ate acabar ou dar erro ----
            base_url = captured["url"]
            headers = captured["headers"]

            all_records: list[dict[str, Any]] = []
            seen: set[Any] = set()

            def add_records(recs: list[dict[str, Any]]) -> int:
                novos = 0
                for r in recs:
                    key = _record_id(r)
                    if key not in seen:
                        seen.add(key)
                        all_records.append(r)
                        novos += 1
                return novos

            # pagina 0 (a que o portal ja carregou)
            page0 = extract_records(captured["body"])
            add_records(page0)
            print(f"  [paginacao] offset=0 -> {len(page0)} registro(s)")

            offset = 1
            while offset < MAX_PAGES:
                url = _set_offset(base_url, offset)
                try:
                    resp = await context.request.get(url, headers=headers, timeout=30000)
                except Exception as exc:
                    print(f"  [paginacao] offset={offset} falhou ({exc}); parando.")
                    break

                if resp.status >= 400:
                    print(f"  [paginacao] offset={offset} -> HTTP {resp.status}; fim.")
                    break

                try:
                    body = await resp.json()
                except Exception:
                    print(f"  [paginacao] offset={offset} -> resposta nao-JSON; fim.")
                    break

                recs = extract_records(body)
                if not recs:
                    print(f"  [paginacao] offset={offset} -> 0 registro(s); fim.")
                    break

                novos = add_records(recs)
                print(
                    f"  [paginacao] offset={offset} -> {len(recs)} registro(s) "
                    f"({novos} novo(s), total={len(all_records)})"
                )
                if novos == 0:
                    print("  [paginacao] nenhum registro novo; fim.")
                    break

                offset += 1
                await page.wait_for_timeout(200)  # pausa educada entre requisicoes
            else:
                print(f"  [paginacao] limite de seguranca de {MAX_PAGES} paginas atingido.")

            captured["records"] = all_records
            captured["pages"] = offset

            # ---- Descricoes: enriquece cada produto via /api/products/{id} ----
            print(
                f"[3/3] Buscando descricoes de {len(all_records)} produto(s) "
                f"(concorrencia={config.DETAIL_CONCURRENCY})..."
            )
            try:
                filled = await _enrich_descriptions(context, all_records, headers)
                print(f"  [descricoes] {filled} produto(s) com descricao preenchida")
            except Exception as exc:
                print(f"  [descricoes] falha ao enriquecer descricoes ({exc}); seguindo sem.")

            # ---- Categorias: lista completa via API (mesma sessao autenticada)
            categories: list[dict[str, Any]] = []
            try:
                resp = await context.request.get(
                    config.CATEGORIES_API, headers=headers, timeout=30000
                )
                if resp.status < 400:
                    body = await resp.json()
                    if isinstance(body, list):
                        categories = [c for c in body if isinstance(c, dict)]
                    print(f"  [categorias] {len(categories)} categoria(s) da API")
                else:
                    print(
                        f"  [categorias] API retornou HTTP {resp.status}; "
                        f"usara fallback dos produtos."
                    )
            except Exception as exc:
                print(
                    f"  [categorias] falha ao buscar categorias ({exc}); "
                    f"usara fallback dos produtos."
                )
            captured["categories"] = categories
        finally:
            await context.close()
            await browser.close()

    return captured


def _record_count(body: Any) -> int:
    """Conta quantos registros existem numa resposta (lista ou objeto paginado)."""
    records = extract_records(body)
    return len(records)


def extract_records(body: Any) -> list[dict[str, Any]]:
    """Extrai a lista de produtos de uma resposta que pode vir em varios formatos."""
    if body is None:
        return []
    if isinstance(body, list):
        return [r for r in body if isinstance(r, dict)]
    if isinstance(body, dict):
        for key in ("data", "items", "results", "products", "rows", "content", "records"):
            value = body.get(key)
            if isinstance(value, list):
                return [r for r in value if isinstance(r, dict)]
            # Estruturas aninhadas tipo {"data": {"items": [...]}}
            if isinstance(value, dict):
                nested = extract_records(value)
                if nested:
                    return nested
        # Se o proprio dict parece um unico registro
        if any(not isinstance(v, (dict, list)) for v in body.values()):
            return [body]
    return []


def run_capture() -> None:
    """Ponto de entrada: captura (paginando) e salva o JSON em disco."""
    result = asyncio.run(capture())

    # Salva a resposta bruta da 1a pagina (referencia do formato original)
    config.RAW_RESPONSE_JSON.write_text(
        json.dumps(result["body"], ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Salva todos os registros de todas as paginas (deduplicados)
    records = result.get("records", extract_records(result["body"]))
    config.PRODUCTS_JSON.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Salva as categorias: lista da API + reforco derivado dos produtos
    # (deduplicado por id em save_categories).
    from .categories import CATEGORIES_JSON, categories_from_products, save_categories

    cats = list(result.get("categories") or [])
    cats += categories_from_products()
    saved = save_categories(cats)

    print(
        f"\nOK! {len(records)} produto(s) capturado(s) em {result.get('pages', 1)} pagina(s).\n"
        f"  - Resposta bruta (1a pagina): {config.RAW_RESPONSE_JSON}\n"
        f"  - Registros (todas paginas):  {config.PRODUCTS_JSON}\n"
        f"  - Categorias ({len(saved)}):          {CATEGORIES_JSON}"
    )


async def _fill_descriptions() -> int:
    """Faz login e preenche `description` no products.json JA capturado.

    Util para enriquecer as descricoes sem refazer a paginacao completa: so
    faz login, captura os headers de autenticacao da 1a chamada de produtos e
    busca o detalhe (/api/products/{id}) de cada produto existente.
    """
    if not config.PRODUCTS_JSON.exists():
        raise RuntimeError(
            f"{config.PRODUCTS_JSON} nao encontrado. Rode a captura primeiro."
        )
    records = json.loads(config.PRODUCTS_JSON.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not records:
        raise RuntimeError("products.json vazio ou invalido.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=config.HEADLESS)
        context = await browser.new_context()
        page = await context.new_page()

        # Captura os headers de auth da 1a resposta de productsWorkspaces.
        headers_box: dict[str, dict[str, str]] = {}
        got_headers = asyncio.Event()

        async def on_response(response: Response) -> None:
            if response.url.startswith(config.API_PREFIX) and response.request.method == "GET":
                if "h" not in headers_box:
                    headers_box["h"] = _auth_headers(await response.request.all_headers())
                    got_headers.set()

        page.on("response", on_response)

        try:
            await _do_login(page)

            # Navega ate Produtos para disparar a chamada da API e obter headers.
            clicked = False
            for sel in ["a:has-text('Produtos')", "nav >> text=Produtos", "[href*='products']", "text=Produtos"]:
                loc = page.locator(sel).first
                try:
                    if await loc.count() > 0 and await loc.is_visible():
                        await loc.click()
                        clicked = True
                        break
                except Exception:
                    continue
            if not clicked:
                await page.goto(config.PRODUCTS_URL, wait_until="networkidle")

            try:
                await asyncio.wait_for(got_headers.wait(), timeout=30)
            except asyncio.TimeoutError:
                pass
            page.remove_listener("response", on_response)

            headers = headers_box.get("h", {})
            if not headers:
                raise RuntimeError(
                    "Nao foi possivel obter os headers de autenticacao. Veja ./debug."
                )

            print(
                f"Buscando descricoes de {len(records)} produto(s) "
                f"(concorrencia={config.DETAIL_CONCURRENCY})..."
            )
            filled = await _enrich_descriptions(context, records, headers)
        finally:
            await context.close()
            await browser.close()

    config.PRODUCTS_JSON.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return filled


def run_fill_descriptions() -> None:
    """Ponto de entrada: enriquece as descricoes do products.json existente."""
    filled = asyncio.run(_fill_descriptions())
    print(f"\nOK! {filled} produto(s) com descricao preenchida em {config.PRODUCTS_JSON}.")


if __name__ == "__main__":
    run_capture()
