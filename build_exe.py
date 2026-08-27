"""
Script para compilar o Gerador IPTV em um executavel (.exe) 100% standalone e portavel
Nao requer Python, Git ou dependencias instaladas na maquina do usuario final.
"""

import os
import sys
import subprocess


def build():
    print("=" * 65)
    print("   COMPILADOR STANDALONE - GERADOR IPTV (.EXE)")
    print("=" * 65)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Verificar / Instalar PyInstaller
    try:
        import PyInstaller
        print("[OK] PyInstaller encontrado.")
    except ImportError:
        print("[*] Instalando PyInstaller no ambiente...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # 2. Arquivos de dados a serem empacotados
    index_html = os.path.join(base_dir, "index.html")
    logo_png = os.path.join(base_dir, "logo.png")
    
    datas = []
    if os.path.exists(index_html):
        datas.append(f"{index_html};.")
    if os.path.exists(logo_png):
        datas.append(f"{logo_png};.")
        
    apps_dir = os.path.join(base_dir, "apps")
    if os.path.exists(apps_dir):
        datas.append(f"{apps_dir};apps")

    tools_dir = os.path.join(base_dir, "tools")
    if os.path.exists(tools_dir):
        datas.append(f"{tools_dir};tools")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=Gerador_IPTV",
        "--onefile",
        "--clean",
    ]
    
    for d in datas:
        cmd.extend(["--add-data", d])
        
    # Dependencias e imports dinamicos do Uvicorn / FastAPI / Crypto
    hidden_imports = [
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "fastapi",
        "fastapi.staticfiles",
        "starlette",
        "starlette.staticfiles",
        "pydantic",
        "requests",
        "Crypto",
        "Crypto.Cipher.DES"
    ]
    for h in hidden_imports:
        cmd.extend(["--hidden-import", h])
        
    cmd.append(os.path.join(base_dir, "server.py"))
    
    print("\n[+] Iniciando processo de empacotamento...")
    res = subprocess.run(cmd, cwd=base_dir)
    if res.returncode == 0:
        exe_path = os.path.join(base_dir, "dist", "Gerador_IPTV.exe")
        print("\n" + "=" * 65)
        print("  COMPILACAO CONCLUIDA COM SUCESSO!")
        print(f"  Executavel gerado: {exe_path}")
        print("  Basta distribuir esse unico arquivo .exe para os usuarios!")
        print("=" * 65)
    else:
        print("\n[!] Falha na compilacao.")


if __name__ == "__main__":
    build()
