"""Configuracoes do projeto integration (lidas do .env)."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

UNIFIED_DATABASE_URL = os.getenv(
    "UNIFIED_DATABASE_URL",
    "postgresql://postgres:123456@localhost:5432/unified_catalog",
)

SHOPIFY_STORE_DOMAIN = os.getenv("SHOPIFY_STORE_DOMAIN", "").strip()
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN", "").strip()
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2026-04").strip()
SHOPIFY_CREATE_STATUS = os.getenv("SHOPIFY_CREATE_STATUS", "DRAFT").strip().upper()

PORT = int(os.getenv("PORT", "5005"))

# --- Groq (traducao de descricoes via IA) --------------------------------- #
# API compativel com OpenAI: POST {GROQ_API_URL} com Authorization Bearer.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
GROQ_API_URL = os.getenv(
    "GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions"
).strip()

# CDN do EcomHub para montar URLs absolutas de imagens
# Imagens ficam em: {CDN}/public/products/{filename}__w-800.png
ECOMHUB_CDN_URL = os.getenv("ECOMHUB_CDN_URL", "https://dropstudio360.fra1.digitaloceanspaces.com").strip()

# Integracoes suportadas (devem casar com a coluna `integration` da tabela unificada)
INTEGRATIONS = ("ecomhub", "primecod")


def has_shopify_credentials() -> bool:
    return bool(SHOPIFY_STORE_DOMAIN and SHOPIFY_ACCESS_TOKEN)


def has_groq_credentials() -> bool:
    return bool(GROQ_API_KEY)


def db_connect_kwargs() -> dict[str, object]:
    """Converte a URL do Postgres em kwargs para psycopg2.connect.

    Ignora parametros de query (ex.: ?schema=public) que o libpq nao entende.
    """
    parsed = urlparse(UNIFIED_DATABASE_URL)
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "user": unquote(parsed.username or "postgres"),
        "password": unquote(parsed.password or ""),
        "dbname": parsed.path.lstrip("/") or "postgres",
    }
