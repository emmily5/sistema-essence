#!/usr/bin/env bash
# Sistema Essence - inicializador para Mac e Linux
cd "$(dirname "$0")" || exit 1

echo "=========================================================="
echo "   SISTEMA ESSENCE - Gestao de Perfumes"
echo "=========================================================="
echo

# --- Verifica o Python ---
if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "[ERRO] O Python nao foi encontrado."
    echo "Instale em: https://www.python.org/downloads/"
    exit 1
fi

# --- Cria o ambiente virtual na primeira execucao ---
if [ ! -d "venv" ]; then
    echo "Preparando o sistema pela primeira vez. Aguarde..."
    "$PY" -m venv venv
    # shellcheck disable=SC1091
    source venv/bin/activate
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt
else
    # shellcheck disable=SC1091
    source venv/bin/activate
fi

# --- Abre o navegador automaticamente ---
URL="http://127.0.0.1:8000"
( sleep 2
  if command -v open >/dev/null 2>&1; then open "$URL"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL"
  fi ) &

echo
echo "Sistema iniciando... O navegador vai abrir sozinho."
echo "Para ENCERRAR, pressione Ctrl+C nesta janela."
echo

"$PY" app.py
