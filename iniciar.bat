@echo off
chcp 65001 >nul
title Sistema Essence
cd /d "%~dp0"

echo ==========================================================
echo    SISTEMA ESSENCE - Gestao de Perfumes
echo ==========================================================
echo.

REM --- Verifica se o Python esta instalado ---
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] O Python nao foi encontrado no seu computador.
    echo.
    echo Para usar o sistema, instale o Python primeiro:
    echo   1. Acesse: https://www.python.org/downloads/
    echo   2. Baixe e instale (MARQUE a opcao "Add Python to PATH"^)
    echo   3. Depois execute este arquivo novamente.
    echo.
    pause
    exit /b
)

REM --- Cria o ambiente virtual na primeira execucao ---
if not exist "venv\" (
    echo Preparando o sistema pela primeira vez. Aguarde um momento...
    python -m venv venv
    call venv\Scripts\activate.bat
    python -m pip install --quiet --upgrade pip
    python -m pip install --quiet -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

REM --- Abre o navegador automaticamente ---
start "" http://127.0.0.1:8000

echo.
echo Sistema iniciando... O navegador vai abrir sozinho.
echo Para ENCERRAR o sistema, feche esta janela preta.
echo.

python app.py

pause
