#!/bin/bash
# Script para sincronizar Primecod de forma automática
# 
# Uso no cron:
#   # Executar todo dia às 2 AM
#   0 2 * * * /path/to/primecod/sync.sh >> /path/to/primecod/logs/sync.log 2>&1

set -e

# Configurações
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
VENV_DIR="$SCRIPT_DIR/venv"
PYTHON_EXECUTABLE="$VENV_DIR/bin/python"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Criar pasta de logs se não existir
mkdir -p "$LOG_DIR"

# Função de logging
log() {
    echo "[$TIMESTAMP] $1" | tee -a "$LOG_DIR/sync.log"
}

# Função de erro
error() {
    echo "[$TIMESTAMP] ❌ ERRO: $1" | tee -a "$LOG_DIR/sync.log"
    exit 1
}

# Verificar se venv existe
if [ ! -d "$VENV_DIR" ]; then
    error "Virtual environment não encontrado em $VENV_DIR"
fi

# Ativar venv
source "$VENV_DIR/bin/activate"

# Mudar para diretório do projeto
cd "$SCRIPT_DIR"

# Executar o pipeline
log "📅 Iniciando sincronização Primecod..."

if $PYTHON_EXECUTABLE main.py all >> "$LOG_DIR/sync.log" 2>&1; then
    log "✅ Sincronização concluída com sucesso!"
    
    # Contar produtos
    COUNT=$($PYTHON_EXECUTABLE -c "
import json
from pathlib import Path
products = json.loads(Path('data/products.json').read_text())
print(len(products))
" 2>/dev/null || echo "?")
    
    log "📊 Total de produtos: $COUNT"
else
    error "Falha na sincronização. Verifique os logs para mais detalhes."
fi
