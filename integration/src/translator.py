"""Traducao de descricoes de produtos via API do Groq.

A API do Groq e compativel com a da OpenAI (chat/completions), entao chamamos
o endpoint diretamente com `requests`. Equivale ao exemplo (SDK JS):

    client.chat.completions.create({
      model: "llama-3.3-70b-versatile",
      messages: [{ role: "user", content: "Translate to Spanish: ..." }]
    })
"""

from __future__ import annotations

import requests

from . import config


class TranslationError(RuntimeError):
    """Erro de configuracao ou de chamada ao Groq."""


# Pais de destino -> idioma alvo da traducao.
COUNTRIES: list[dict[str, str]] = [
    {"code": "es", "name": "Espanha", "language": "Spanish"},
    {"code": "pt", "name": "Portugal", "language": "Portuguese"},
    {"code": "it", "name": "Itália", "language": "Italian"},
    {"code": "fr", "name": "França", "language": "French"},
    {"code": "de", "name": "Alemanha", "language": "German"},
    {"code": "gb", "name": "Reino Unido", "language": "English"},
    {"code": "us", "name": "Estados Unidos", "language": "English"},
    {"code": "nl", "name": "Holanda", "language": "Dutch"},
    {"code": "pl", "name": "Polônia", "language": "Polish"},
    {"code": "ro", "name": "Romênia", "language": "Romanian"},
    {"code": "gr", "name": "Grécia", "language": "Greek"},
    {"code": "sa", "name": "Arábia Saudita", "language": "Arabic"},
    {"code": "br", "name": "Brasil", "language": "Portuguese"},
]

_BY_CODE = {c["code"]: c for c in COUNTRIES}


def language_for_country(code: str) -> str | None:
    """Retorna o idioma alvo (ex.: 'Spanish') para o codigo do pais."""
    country = _BY_CODE.get((code or "").strip().lower())
    return country["language"] if country else None


def _chat(messages: list[dict[str, str]], temperature: float = 0.2) -> str:
    """Chama o chat/completions do Groq e devolve o conteudo da resposta."""
    if not config.GROQ_API_KEY:
        raise TranslationError("GROQ_API_KEY não configurada no .env.")

    payload = {
        "model": config.GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {config.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(config.GROQ_API_URL, json=payload, headers=headers, timeout=60)
    except requests.RequestException as exc:
        raise TranslationError(f"Falha ao chamar o Groq: {exc}") from exc

    if resp.status_code >= 400:
        raise TranslationError(f"Groq retornou HTTP {resp.status_code}: {resp.text[:300]}")

    try:
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise TranslationError(f"Resposta inesperada do Groq: {resp.text[:300]}") from exc


def translate(text: str, language: str) -> str:
    """Traduz `text` para `language` usando o Groq e devolve so o texto traduzido."""
    if not text or not text.strip():
        raise TranslationError("Produto sem descrição para traduzir.")
    return _chat(
        [
            {
                "role": "system",
                "content": (
                    "You are a professional translator. Return ONLY the translated "
                    "text, preserving any HTML markup AND keeping every icon/emoji "
                    "exactly as it appears in the source, in the same positions, "
                    "with no comments or explanations."
                ),
            },
            {"role": "user", "content": f"Translate to {language}: {text}"},
        ],
        temperature=0.2,
    )


def improve_description(name: str, description: str) -> str:
    """Melhora a descricao do produto (persuasiva/SEO) via Groq e devolve o texto."""
    if not description or not description.strip():
        raise TranslationError("Produto sem descrição para melhorar.")
    return _chat(
        [
            {
                "role": "system",
                "content": (
                    "Você é especialista em e-commerce.\n\n"
                    "Regras:\n"
                    "- Gere descrições persuasivas.\n"
                    "- Não invente características técnicas.\n"
                    "- Utilize SEO.\n"
                    "- Mantenha os ícones/emojis presentes na descrição original.\n"
                    "- Retorne apenas o texto."
                ),
            },
            {
                "role": "user",
                "content": f"Nome: {name or ''}\n\nDescrição Atual:\n{description}",
            },
        ],
        temperature=0.4,
    )
