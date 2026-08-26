@echo off
chcp 65001 >nul
title Compilador Standalone - Gerador IPTV

echo ===================================================================
echo     COMPILADOR DE EXECUTAVEL STANDALONE (.EXE) - GERADOR IPTV
echo ===================================================================
echo.
echo Este script ira gerar um unico arquivo executavel (.exe) que contem
echo todo o Python, bibliotecas, servidor web e interface embutidos.
echo.

python build_exe.py

echo.
pause
