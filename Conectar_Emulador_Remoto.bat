@echo off
chcp 65001 >nul
title Conectar Emulador Local ao Servidor Remoto (config.servidor.xyz.br)
cls

echo =====================================================================
echo   🌐 CONECTAR EMULADOR LOCAL AO SERVIDOR NA NUVEM (VPS)
echo =====================================================================
echo.
echo Este utilitário cria um túnel seguro para o servidor remoto acessar
echo o seu emulador Android local com 1 clique.
echo.
echo [1] MEmu Play (Porta 21503)
echo [2] Nox Player (Porta 62001)
echo [3] LDPlayer (Porta 5555)
echo [4] Outra Porta Customizada
echo.
set /p opt="Escolha o seu emulador (Padrao 1): "
if "%opt%"=="" set opt=1

set PORT=21503
if "%opt%"=="2" set PORT=62001
if "%opt%"=="3" set PORT=5555
if "%opt%"=="4" (
    set /p PORT="Digite o numero da porta ADB: "
)

echo.
echo ---------------------------------------------------------------------
echo 🚀 Iniciando túnel seguro TCP na porta %PORT%...
echo.
echo 👉 Quando abrir o túnel, COPIE o endereço gerado (ex: tcp.pinggy.io:12345)
echo    e cole no campo "Endereço do Dispositivo ADB" no site:
echo    https://config.servidor.xyz.br
echo ---------------------------------------------------------------------
echo.

ssh -p 443 -o StrictHostKeyChecking=no -R0:localhost:%PORT% qr@a.pinggy.io

pause
