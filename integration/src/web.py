"""Interface web (Flask) para revisar SKUs e enviar os marcados a Shopify."""

from __future__ import annotations

import os

from flask import Flask, flash, redirect, render_template, request, url_for

from . import compare, config, db
from .sender import send_skus
from .shopify_client import ShopifyError

_TEMPLATES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
app = Flask(__name__, template_folder=_TEMPLATES)
app.secret_key = "integration-local"  # apenas para flash messages locais


def _current_integration() -> str:
    integ = request.args.get("integration") or config.INTEGRATIONS[0]
    return integ if integ in config.INTEGRATIONS else config.INTEGRATIONS[0]


@app.route("/")
def index():
    integration = _current_integration()
    only = request.args.get("only")  # None | 'missing' | 'present'
    db.ensure_status_table()
    rows = db.fetch_statuses(integration, only=only)
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


def run() -> None:
    app.run(host="127.0.0.1", port=config.PORT, debug=True)
