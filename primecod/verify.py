"""Script de validação de pré-requisitos do Primecod Importer.

Executa checklist antes de rodar o pipeline completo.
"""

import os
import sys
from pathlib import Path

try:
    import requests
    from dotenv import load_dotenv
except ImportError as e:
    print(f"❌ Erro: {e}")
    print("Execute: pip install -r requirements.txt")
    sys.exit(1)

def check_env_file():
    """Verifica se arquivo .env existe e contém variáveis essenciais."""
    print("\n[CHECK] Arquivo .env")
    env_path = Path(".env")
    
    if not env_path.exists():
        print("  ❌ Arquivo .env não encontrado")
        print("  → Execute: cp .env.example .env")
        return False
    
    print("  ✓ Arquivo .env encontrado")
    
    # Carregar variáveis
    load_dotenv()
    
    required_vars = [
        "PRIMECOD_API_TOKEN",
        "DATABASE_URL",
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
            print(f"  ❌ Variável {var} não configurada")
    
    if missing:
        return False
    
    print("  ✓ Todas as variáveis necessárias estão configuradas")
    return True


def check_python_version():
    """Verifica se Python 3.8+ está sendo usado."""
    print("\n[CHECK] Versão Python")
    
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"  ❌ Python {version.major}.{version.minor} detectado")
        print("  → Python 3.8+ é necessário")
        return False
    
    print(f"  ✓ Python {version.major}.{version.minor}.{version.micro}")
    return True


def check_dependencies():
    """Verifica se dependências Python estão instaladas."""
    print("\n[CHECK] Dependências Python")
    
    deps = {
        "dotenv": "python-dotenv",
        "requests": "requests",
        "prisma": "prisma",
    }
    
    missing = []
    for module, package in deps.items():
        try:
            __import__(module)
            print(f"  ✓ {package}")
        except ImportError:
            missing.append(package)
            print(f"  ❌ {package}")
    
    if missing:
        print(f"\n  → Execute: pip install {' '.join(missing)}")
        return False
    
    return True


def check_directories():
    """Verifica se estrutura de diretórios está completa."""
    print("\n[CHECK] Diretórios")
    
    dirs = ["src", "prisma", "data", "debug"]
    missing = []
    
    for d in dirs:
        if Path(d).exists():
            print(f"  ✓ Diretório '{d}/'")
        else:
            missing.append(d)
            print(f"  ❌ Diretório '{d}/' não encontrado")
    
    if missing:
        print(f"\n  → Execute: mkdir {' '.join(missing)}")
        return False
    
    return True


def check_api_connectivity():
    """Verifica se consegue conectar à API Primecod."""
    print("\n[CHECK] Conectividade API")
    
    load_dotenv()
    api_url = os.getenv("PRIMECOD_API_URL")
    token = os.getenv("PRIMECOD_API_TOKEN")
    token_type = os.getenv("PRIMECOD_API_TOKEN_TYPE", "Bearer")
    
    if not api_url or not token:
        print("  ⚠️  Variáveis de API não configuradas")
        return False
    
    try:
        headers = {
            "Authorization": f"{token_type} {token}",
            "Accept": "application/json",
        }
        
        response = requests.get(
            api_url,
            params={"page": 1, "per_page": 1},
            headers=headers,
            timeout=10,
        )
        
        if response.status_code == 200:
            print(f"  ✓ API conectada (HTTP {response.status_code})")
            data = response.json()
            total = data.get("total", "?")
            print(f"  ✓ Total de produtos na API: {total}")
            return True
        elif response.status_code == 401:
            print(f"  ❌ Token inválido (HTTP 401)")
            print("  → Verifique PRIMECOD_API_TOKEN no .env")
            return False
        else:
            print(f"  ⚠️  API respondeu com HTTP {response.status_code}")
            return True
            
    except requests.ConnectionError:
        print("  ❌ Não conseguiu conectar à API")
        print("  → Verifique sua conexão com internet")
        return False
    except requests.Timeout:
        print("  ⚠️  API não respondeu em tempo (timeout)")
        return True
    except Exception as e:
        print(f"  ⚠️  Erro ao conectar: {e}")
        return True


def check_database():
    """Verifica se consegue conectar ao PostgreSQL."""
    print("\n[CHECK] Banco de Dados PostgreSQL")
    
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        print("  ❌ DATABASE_URL não configurado")
        return False
    
    try:
        # Tentar importar psycopg (driver PostgreSQL)
        try:
            import psycopg
            print(f"  ✓ Driver PostgreSQL disponível (psycopg)")
        except ImportError:
            print(f"  ⚠️  Driver PostgreSQL não instalado")
            print(f"     (será instalado pelo Prisma automaticamente)")
        
        # Não tentamos conectar aqui porque pode não ter o driver ainda
        # O Prisma vai fazer isso quando rodar db push
        
        print(f"  ✓ DATABASE_URL configurado")
        return True
        
    except Exception as e:
        print(f"  ⚠️  Erro ao verificar banco: {e}")
        return True


def check_src_files():
    """Verifica se arquivos Python estão presentes."""
    print("\n[CHECK] Arquivos Python")
    
    files = {
        "src/__init__.py": "Inicialização",
        "src/config.py": "Configuração",
        "src/api_client.py": "Cliente API",
        "src/schema_generator.py": "Gerador Schema",
        "src/importer.py": "Importador",
        "main.py": "Orquestrador",
    }
    
    missing = []
    for filepath, description in files.items():
        if Path(filepath).exists():
            print(f"  ✓ {filepath} ({description})")
        else:
            missing.append(filepath)
            print(f"  ❌ {filepath} ({description})")
    
    if missing:
        return False
    
    return True


def main():
    """Execute todos os checks."""
    print("=" * 60)
    print("🔍 VALIDAÇÃO DE PRÉ-REQUISITOS - Primecod Importer")
    print("=" * 60)
    
    checks = [
        ("Python", check_python_version),
        ("Arquivo .env", check_env_file),
        ("Dependências", check_dependencies),
        ("Diretórios", check_directories),
        ("Arquivos Python", check_src_files),
        ("API Primecod", check_api_connectivity),
        ("Banco PostgreSQL", check_database),
    ]
    
    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"  ❌ Erro durante verificação: {e}")
            results[name] = False
    
    # Resumo
    print("\n" + "=" * 60)
    print("📋 RESUMO")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        icon = "✓" if result else "✗"
        print(f"  {icon} {name}")
    
    print(f"\nTotal: {passed}/{total} verificações passaram")
    
    if passed == total:
        print("\n✅ Tudo pronto! Execute: python main.py all")
        return 0
    elif passed >= total - 2:
        print("\n⚠️  Alguns avisos, mas pode tentar rodar: python main.py all")
        return 0
    else:
        print("\n❌ Corrija os erros acima e tente novamente")
        return 1


if __name__ == "__main__":
    sys.exit(main())
