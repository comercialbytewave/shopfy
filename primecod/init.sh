#!/bin/bash
# Script de inicialização rápida para o Primecod Importer

set -e  # Parar no primeiro erro

echo "======================================"
echo "Primecod Importer - Inicialização"
echo "======================================"

# 1. Verificar se .env existe
if [ ! -f .env ]; then
    echo "⚠️  Arquivo .env não encontrado!"
    echo "Copiando .env.example para .env..."
    cp .env.example .env
    echo "✓ Arquivo .env criado"
    echo ""
    echo "⚠️  IMPORTANTE: Edite o arquivo .env com suas credenciais!"
    echo "   - Configure PRIMECOD_API_TOKEN"
    echo "   - Configure DATABASE_URL"
    exit 1
fi

# 2. Verificar se Python está disponível
if ! command -v python &> /dev/null; then
    echo "❌ Python não encontrado!"
    exit 1
fi

echo "✓ Python encontrado: $(python --version)"

# 3. Criar venv se não existir
if [ ! -d venv ]; then
    echo "Criando virtual environment..."
    python -m venv venv
    echo "✓ Virtual environment criado"
fi

# 4. Ativar venv
echo "Ativando virtual environment..."
source venv/bin/activate

# 5. Instalar dependências
echo "Instalando dependências..."
pip install -r requirements.txt > /dev/null 2>&1
echo "✓ Dependências instaladas"

# 6. Executar o pipeline
echo ""
echo "======================================"
echo "Iniciando pipeline..."
echo "======================================"
echo ""

python main.py all

echo ""
echo "======================================"
echo "✓ Pipeline concluído com sucesso!"
echo "======================================"
