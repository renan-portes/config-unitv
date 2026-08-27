@echo off
chcp 65001 > nul
title "Gerador de .config IPTV"
set "PATH=%~dp0tools;%PATH%"

echo ================================================================
echo           GERADOR DE .CONFIG / .PROPERTIES / XML
echo ================================================================
echo.
echo [1/3] Verificando ambiente Python...
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado no sistema!
    echo Instale o Python em https://python.org e marque 'Add to PATH'.
    echo Pressione qualquer tecla para sair...
    pause > nul
    exit /b 1
)

echo [2/3] Verificando dependencias necessarias...
pip install -r requirements.txt --quiet

echo.
echo [3/3] Iniciando servidor do Gerador...
echo.
echo Servidor ativo em: http://localhost:8000
echo.

python server.py

pause
