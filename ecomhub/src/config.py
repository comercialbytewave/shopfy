"""Carrega as configuracoes do projeto a partir do arquivo .env."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Raiz do projeto (pasta que contem este arquivo .env)
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DEBUG_DIR = ROOT_DIR / "debug"
PRISMA_DIR = ROOT_DIR / "prisma"

# Carrega variaveis do .env
load_dotenv(ROOT_DIR / ".env")


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Variavel de ambiente '{name}' nao encontrada. "
            f"Copie .env.example para .env e preencha os valores."
        )
    return value


# Credenciais: lidas sob demanda (somente a etapa de captura precisa delas).
EMAIL = os.getenv("ECOMHUB_EMAIL", "")
PASSWORD = os.getenv("ECOMHUB_PASSWORD", "")


def require_credentials() -> tuple[str, str]:
    """Valida e retorna (email, senha). Chamado apenas na captura."""
    return _require("ECOMHUB_EMAIL"), _require("ECOMHUB_PASSWORD")


# URLs (com defaults sensatos)
LOGIN_URL = os.getenv("ECOMHUB_LOGIN_URL", "https://go.ecomhub.app/login")
PRODUCTS_URL = os.getenv("ECOMHUB_PRODUCTS_URL", "https://go.ecomhub.app/products")
API_PREFIX = os.getenv(
    "ECOMHUB_API_PREFIX", "https://api.ecomhub.app/api/productsWorkspaces"
)

# Banco
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Navegador
HEADLESS = os.getenv("HEADLESS", "true").strip().lower() in ("1", "true", "yes", "sim")

# Arquivos gerados
PRODUCTS_JSON = DATA_DIR / "products.json"
RAW_RESPONSE_JSON = DATA_DIR / "products_raw.json"

# Garante que as pastas existam
DATA_DIR.mkdir(parents=True, exist_ok=True)
DEBUG_DIR.mkdir(parents=True, exist_ok=True)
