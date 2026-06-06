"""Interface web (Flask) para revisar SKUs e enviar os marcados a Shopify."""

from __future__ import annotations

import os
from collections import OrderedDict

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

from . import compare, config, db, translator
from .sender import send_skus
from .shopify_client import ShopifyError

_TEMPLATES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
app = Flask(__name__, template_folder=_TEMPLATES)
app.secret_key = "integration-local"  # apenas para flash messages locais


def _group_ecomhub_rows(rows: list[dict]) -> list[dict]:
    """Agrupa variantes ecomhub em 1 linha por produto com lista de variantes expandível.

    Para o form de envio usa o primeiro SKU como representante — o sender.py
    busca todas as variantes via product_pk ao processar.
    """
    groups: dict = OrderedDict()
    for r in rows:
        pk = r.get("product_pk") or 0
        if pk not in groups:
            groups[pk] = {
                "product_pk": pk,
                "product_id": r.get("product_id"),
                "product_name": r.get("product_name"),
                "sku": r["sku"],
                "price": r.get("price"),
                "variant_count": 0,
                "in_shopify": True,
                "sent": False,
                "selected": r.get("selected", False),
                "_rows": [],
            }
        g = groups[pk]
        g["variant_count"] += 1
        g["_rows"].append(r)
        if not r.get("in_shopify"):
            g["in_shopify"] = False
        if r.get("sent"):
            g["sent"] = True

    result = []
    for pk, g in groups.items():
        if g["variant_count"] > 1:
            # Busca labels (atributos) na tabela products para exibir no dropdown
            product = db.get_product_by_pk("ecomhub", pk)
            label_map = {}
            if product:
                label_map = {v["sku"]: v["label"] for v in product.get("variants", [])}
            g["variants"] = [
                {
                    "sku": r["sku"],
                    "label": label_map.get(r["sku"], r["sku"]),
                    "in_shopify": r.get("in_shopify", False),
                    "sent": r.get("sent", False),
                }
                for r in g["_rows"]
            ]
        else:
            g["variants"] = []
        del g["_rows"]
        result.append(g)

    return result


def _current_integration() -> str:
    integ = request.args.get("integration") or config.INTEGRATIONS[0]
    return integ if integ in config.INTEGRATIONS else config.INTEGRATIONS[0]


@app.route("/")
def index():
    integration = _current_integration()
    only = request.args.get("only")  # None | 'missing' | 'present'
    db.ensure_status_table()
    rows = db.fetch_statuses(integration, only=only)
    if integration == "ecomhub":
        rows = _group_ecomhub_rows(rows)

    # Anexa descricao + traducao (da tabela products) a cada linha da listagem.
    # Indexado por product_id (chave natural estavel), nao por pk.
    text_map = db.get_products_text(integration, [r.get("product_id") for r in rows])
    for r in rows:
        info = text_map.get(r.get("product_id")) or {}
        r["description"] = info.get("description")
        r["description_translate"] = info.get("description_translate")
        r["language_translate"] = info.get("language_translate")
        r["description_upgrade"] = info.get("description_upgrade")
        r["description_upgrade_translate"] = info.get("description_upgrade_translate")

    stats = db.counts(integration)
    return render_template(
        "index.html",
        integrations=config.INTEGRATIONS,
        integration=integration,
        rows=rows,
        stats=stats,
        only=only or "all",
        has_creds=config.has_shopify_credentials(),
        store=config.SHOPIFY_STORE_DOMAIN,
        has_groq=config.has_groq_credentials(),
        countries=translator.COUNTRIES,
    )


@app.route("/sync", methods=["POST"])
def sync():
    integration = _current_integration()
    try:
        res = compare.run_sync(integration)
        flash(
            f"Sincronizado: {res['total']} SKU(s), {res['present']} na Shopify, "
            f"{res['missing']} faltando.",
            "ok",
        )
    except Exception as exc:  # noqa: BLE001 - mostra erro na UI
        flash(f"Erro ao sincronizar: {exc}", "err")
    return redirect(url_for("index", integration=integration, only=request.args.get("only")))


@app.route("/send", methods=["POST"])
def send():
    integration = request.form.get("integration") or config.INTEGRATIONS[0]
    skus = request.form.getlist("skus")
    if not skus:
        flash("Nenhum item marcado.", "err")
        return redirect(url_for("index", integration=integration))
    try:
        res = send_skus(integration, skus)
        msg = f"Criados: {len(res['created'])}; ignorados: {len(res['skipped'])}; erros: {len(res['errors'])}."
        flash(msg, "ok" if not res["errors"] else "err")
        for e in res["errors"][:5]:
            flash(f"  {e['sku']}: {e['error']}", "err")
    except ShopifyError as exc:
        flash(f"Shopify: {exc}", "err")
    except Exception as exc:  # noqa: BLE001
        flash(f"Erro ao enviar: {exc}", "err")
    return redirect(url_for("index", integration=integration, only="missing"))


@app.route("/translate", methods=["POST"])
def translate_product():
    """Traduz a descricao de um produto para o idioma do pais de destino.

    Recebe (form): integration, product_pk, country (codigo). Busca a descricao
    na tabela products, traduz via Groq, grava em description_translate /
    language_translate e devolve o texto traduzido em JSON.
    """
    integration = request.form.get("integration") or config.INTEGRATIONS[0]
    product_id = (request.form.get("product_id") or "").strip()
    country = request.form.get("country", "")

    if not product_id:
        return jsonify(ok=False, error="Produto inválido."), 400

    language = translator.language_for_country(country)
    if not language:
        return jsonify(ok=False, error="País de destino inválido."), 400

    product = db.get_product_description(integration, product_id)
    if not product:
        return jsonify(ok=False, error="Produto não encontrado."), 404

    desc = (product.get("description") or "").strip()
    upgrade = (product.get("description_upgrade") or "").strip()
    if not desc and not upgrade:
        return jsonify(ok=False, error="Produto sem descrição para traduzir."), 400

    try:
        # Traduz a descricao original e, se existir, tambem a descricao melhorada.
        translated = translator.translate(desc, language) if desc else None
        upgrade_translation = translator.translate(upgrade, language) if upgrade else None
    except translator.TranslationError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    except Exception as exc:  # noqa: BLE001
        return jsonify(ok=False, error=f"Erro inesperado: {exc}"), 500

    db.save_translation(integration, product_id, translated, language, upgrade_translation)
    return jsonify(
        ok=True,
        language=language,
        product_name=product.get("name"),
        translation=translated,
        upgrade_translation=upgrade_translation,
    )


@app.route("/improve", methods=["POST"])
def improve_product():
    """Melhora a descricao de um produto (persuasiva/SEO) via Groq.

    Recebe (form): integration, product_id. Busca nome + descricao na tabela
    products, melhora via Groq, grava em description_upgrade e devolve o texto.
    """
    integration = request.form.get("integration") or config.INTEGRATIONS[0]
    product_id = (request.form.get("product_id") or "").strip()

    if not product_id:
        return jsonify(ok=False, error="Produto inválido."), 400

    product = db.get_product_description(integration, product_id)
    if not product:
        return jsonify(ok=False, error="Produto não encontrado."), 404

    try:
        improved = translator.improve_description(
            product.get("name") or "", product.get("description") or ""
        )
    except translator.TranslationError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    except Exception as exc:  # noqa: BLE001
        return jsonify(ok=False, error=f"Erro inesperado: {exc}"), 500

    db.save_description_upgrade(integration, product_id, improved)
    return jsonify(ok=True, product_name=product.get("name"), upgrade=improved)


def run() -> None:
    app.run(host="127.0.0.1", port=config.PORT, debug=True)
