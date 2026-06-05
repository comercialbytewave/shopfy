import os
import json
import datetime
from pathlib import Path
import requests
from dotenv import load_dotenv

# Caminho para o diretório atual
CURRENT_DIR = Path(__file__).resolve().parent

# Tenta carregar o arquivo .env
env_path = CURRENT_DIR / ".env"
load_dotenv(env_path)

def get_env_var(name: str) -> str:
    """Busca uma variável de ambiente tentando variações de nome (ex: SHOPIFY_CODE, CODE, code)."""
    variations = [
        f"SHOPIFY_{name.upper()}",
        name.upper(),
        name.lower()
    ]
    for var in variations:
        val = os.getenv(var)
        if val:
            return val.strip()
    return ""

def main():
    # Carrega variáveis
    url_domain = get_env_var("url_domain")
    client_id = get_env_var("client_id")
    client_secret = get_env_var("client_secret")
    code = get_env_var("code")

    # Verifica se todas as variáveis estão preenchidas
    missing = []
    if not url_domain: missing.append("url_domain (Ex: SHOPIFY_URL_DOMAIN)")
    if not client_id: missing.append("client_id (Ex: SHOPIFY_CLIENT_ID)")
    if not client_secret: missing.append("client_secret (Ex: SHOPIFY_CLIENT_SECRET)")
    if not code: missing.append("code (Ex: SHOPIFY_CODE)")

    if missing:
        print("\n=== [ERRO] Configurações ausentes no arquivo .env ===")
        print("Por favor, preencha as seguintes variáveis no arquivo '.env':")
        for item in missing:
            print(f" - {item}")
        print("===================================================\n")
        return

    # Limpa a URL se o usuário colocou protocolo
    clean_domain = url_domain.replace("https://", "").replace("http://", "").strip("/")
    url = f"https://{clean_domain}/admin/oauth/access_token"

    # Prepara o payload para x-www-form-urlencoded
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code
    }

    print(f"\n--- Iniciando requisição de OAuth para Shopify ---")
    print(f"URL: {url}")
    print(f"Payload (Body): {json.dumps(payload, indent=2)}")

    try:
        # data=payload envia em form url encoding automaticamente
        response = requests.post(url, data=payload, timeout=30)
        
        status_code = response.status_code
        headers = dict(response.headers)
        
        # Tenta decodificar como JSON para exibição mais amigável
        try:
            response_data = response.json()
            response_text = json.dumps(response_data, indent=2)
        except ValueError:
            response_data = None
            response_text = response.text

        # Exibe no console
        print(f"\n=== RETORNO (Status Code: {status_code}) ===")
        print(response_text)
        print("=========================================\n")

        # Gera o arquivo de log
        log_path = CURRENT_DIR / "response.log"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_content = (
            f"=== LOG DE REQUISIÇÃO OAUTH - {timestamp} ===\n"
            f"URL de Destino: {url}\n"
            f"Status Code: {status_code}\n"
            f"Payload Enviado: {payload}\n"
            f"Headers de Resposta:\n{json.dumps(headers, indent=2)}\n"
            f"Corpo da Resposta:\n{response_text}\n"
            f"{'='*50}\n\n"
        )

        # Escreve ou anexa no log
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_content)

        print(f"Arquivo de log atualizado/gerado com sucesso em: {log_path}\n")

    except Exception as e:
        error_msg = f"Erro ao realizar a requisição: {str(e)}"
        print(f"\n[ERRO] {error_msg}\n")
        
        # Registra erro no log também
        log_path = CURRENT_DIR / "response.log"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"=== ERRO OAUTH - {timestamp} ===\n{error_msg}\n{'='*50}\n\n")

if __name__ == "__main__":
    main()
