"""
Servidor Web e API REST para o Gerador de Configurações IPTV & HackDroid
Suporta geração local de novas contas, injeção ADB no emulador e integração com o Pool da Nuvem (10.231 configs)
"""

import os
import io
import json
import base64
import random
import subprocess
import requests
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

import generator_engine as engine

app = FastAPI(
    title="Gerador de .config IPTV (Local, Nuvem & ADB)",
    description="API e Painel Web para geração de .config, .properties e cache.config.xml com suporte a injeção ADB no emulador e pool da nuvem",
    version="1.3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLOUD_IDS_URL = "https://raw.githubusercontent.com/iurysouza041095-bit/sorteio/main/ids.json"
cached_cloud_ids = []


# --- MODELOS DE REQUISIÇÃO ---

class SingleGenerateRequest(BaseModel):
    mac: Optional[str] = None
    folder_name: Optional[str] = "CONFIG_NEW"
    user_id: Optional[str] = None
    channel_code: Optional[str] = "SBTHD"
    fresh_account: bool = True
    device_id_hex: Optional[str] = None


class BulkGenerateRequest(BaseModel):
    count: int = 10
    start_index: int = 1
    folder_prefix: str = "CONFIG_"
    start_mac_byte: Optional[int] = None
    fresh_account: bool = True
    save_to_disk: bool = False


class DecodeRequest(BaseModel):
    hex_string: str


class SaveDiskRequest(BaseModel):
    configs: list
    target_dir: Optional[str] = "."


class ADBInjectRequest(BaseModel):
    config_content: str
    device_addr: Optional[str] = "127.0.0.1:21503"
    clear_cache: bool = True
    launch_app: bool = True


# --- ROTAS DA API ---

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "config-generator", "version": "1.3.0", "mode": "local-cloud-adb"}


@app.get("/api/configs")
def list_existing_configs():
    """Retorna todas as configurações existentes no diretório local"""
    try:
        catalog = engine.load_all_existing_configs(BASE_DIR)
        return {
            "total": len(catalog),
            "configs": catalog
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config-detail")
def get_config_detail(folder: str):
    """Carrega os arquivos de uma pasta existente"""
    folder_clean = folder.replace("..", "").strip("/\\")
    full_path = os.path.join(BASE_DIR, folder_clean)
    
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Pasta não encontrada")
        
    cfg_file = os.path.join(full_path, ".config")
    prop_file = os.path.join(full_path, ".properties")
    xml_file = os.path.join(full_path, "cache.config.xml")
    
    cfg_content = open(cfg_file, 'r', encoding='utf-8', errors='ignore').read() if os.path.exists(cfg_file) else ""
    prop_content = open(prop_file, 'r', encoding='utf-8', errors='ignore').read() if os.path.exists(prop_file) else ""
    xml_content = open(xml_file, 'r', encoding='utf-8', errors='ignore').read() if os.path.exists(xml_file) else ""
    
    return {
        "folder": folder_clean,
        "files": {
            ".config": cfg_content,
            ".properties": prop_content,
            "cache.config.xml": xml_content
        }
    }


@app.post("/api/generate-single")
def generate_single(req: SingleGenerateRequest):
    """Gera uma configuração individual"""
    try:
        result = engine.generate_single_config(
            mac=req.mac,
            folder_name=req.folder_name or "CONFIG_NEW",
            user_id=req.user_id,
            channel_code=req.channel_code or "SBTHD",
            fresh_account=req.fresh_account,
            device_id_hex=req.device_id_hex
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/generate-bulk")
def generate_bulk(req: BulkGenerateRequest):
    """Gera múltiplas configurações"""
    try:
        if req.count < 1 or req.count > 256:
            raise HTTPException(status_code=400, detail="Quantidade deve estar entre 1 e 256")
            
        results = engine.generate_bulk_configs(
            count=req.count,
            start_index=req.start_index,
            folder_prefix=req.folder_prefix,
            start_mac_byte=req.start_mac_byte,
            fresh_account=req.fresh_account
        )
        
        saved_paths = []
        if req.save_to_disk:
            saved_paths = engine.save_configs_to_directory(results, BASE_DIR)
            
        return {
            "total": len(results),
            "configs": results,
            "saved_to_disk": req.save_to_disk,
            "saved_paths": saved_paths
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/download-single-zip")
def download_single_zip(req: SingleGenerateRequest):
    """Gera e faz o streaming de um arquivo .ZIP de uma configuração"""
    try:
        cfg = engine.generate_single_config(
            mac=req.mac,
            folder_name=req.folder_name or "CONFIG_NEW",
            user_id=req.user_id,
            channel_code=req.channel_code or "SBTHD",
            fresh_account=req.fresh_account,
            device_id_hex=req.device_id_hex
        )
        zip_data = engine.create_zip_archive([cfg])
        filename = f"{cfg['folder_name']}.zip"
        
        return Response(
            content=zip_data,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/download-bulk-zip")
def download_bulk_zip(req: BulkGenerateRequest):
    """Gera e faz o streaming de um arquivo .ZIP contendo o lote de configurações"""
    try:
        results = engine.generate_bulk_configs(
            count=req.count,
            start_index=req.start_index,
            folder_prefix=req.folder_prefix,
            start_mac_byte=req.start_mac_byte,
            fresh_account=req.fresh_account
        )
        zip_data = engine.create_zip_archive(results)
        filename = f"pacote_configs_{len(results)}_itens.zip"
        
        return Response(
            content=zip_data,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/download-existing-zip")
def download_existing_zip(folder: str):
    """Baixa uma pasta existente como ZIP"""
    try:
        folder_clean = folder.replace("..", "").strip("/\\")
        full_path = os.path.join(BASE_DIR, folder_clean)
        if not os.path.exists(full_path):
            raise HTTPException(status_code=404, detail="Pasta não encontrada")
            
        files_dict = {}
        for fname in [".config", ".properties", "cache.config.xml"]:
            fpath = os.path.join(full_path, fname)
            if os.path.exists(fpath):
                files_dict[fname] = open(fpath, 'r', encoding='utf-8', errors='ignore').read()
                
        fake_cfg = [{
            "folder_name": os.path.basename(folder_clean),
            "files": files_dict
        }]
        zip_data = engine.create_zip_archive(fake_cfg)
        return Response(
            content=zip_data,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{os.path.basename(folder_clean)}.zip"'}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/decode-hex")
def decode_hex(req: DecodeRequest):
    """Decodifica uma sequência hexadecimal"""
    return engine.decode_hex_value(req.hex_string)


@app.post("/api/save-to-disk")
def save_to_disk(req: SaveDiskRequest):
    """Grava as configurações enviadas fisicamente no diretório"""
    try:
        target = os.path.join(BASE_DIR, req.target_dir) if req.target_dir else BASE_DIR
        paths = engine.save_configs_to_directory(req.configs, target)
        return {
            "success": True,
            "saved_count": len(paths),
            "paths": paths
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- POOL DA NUVEM (10.231 CONFIGS) ---

@app.get("/api/cloud/random")
def get_random_cloud_config():
    """Puxa uma configuração fresca aleatória do pool da nuvem (10.231 disponíveis)"""
    global cached_cloud_ids
    try:
        if not cached_cloud_ids:
            r = requests.get(CLOUD_IDS_URL, timeout=10)
            cached_cloud_ids = r.json().get("arquivos", [])
            
        if not cached_cloud_ids:
            raise HTTPException(status_code=503, detail="Não foi possível obter a lista da nuvem")
            
        chosen_id = random.choice(cached_cloud_ids)
        dl_url = f"https://drive.google.com/uc?export=download&id={chosen_id}"
        res = requests.get(dl_url, timeout=10)
        content = res.text
        
        # Build structure compatible with generator
        folder_name = f"CONFIG_CLOUD_{chosen_id[:6]}"
        files = {
            ".config": content,
            ".properties": content,
            "cache.config.xml": ""
        }
        
        return {
            "source": "cloud",
            "file_id": chosen_id,
            "total_available": len(cached_cloud_ids),
            "folder_name": folder_name,
            "files": files
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar na nuvem: {str(e)}")


# --- ENDPOINTS ADB (EMULADOR) ---

@app.get("/api/adb/devices")
def get_adb_devices():
    """Detecta emuladores e dispositivos Android conectados via ADB"""
    try:
        res = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
        devices = []
        for line in res.stdout.splitlines()[1:]:
            if "\tdevice" in line:
                devices.append(line.split("\t")[0].strip())
        return {
            "connected": len(devices) > 0,
            "devices": devices
        }
    except Exception as e:
        return {"connected": False, "devices": [], "error": str(e)}


@app.post("/api/adb/inject")
def inject_adb(req: ADBInjectRequest):
    """Injeta a .config diretamente no emulador via ADB e inicia o UniTV Free"""
    try:
        device = req.device_addr or "127.0.0.1:21503"
        temp_dir = os.path.join(BASE_DIR, ".temp")
        os.makedirs(temp_dir, exist_ok=True)
        temp_file = os.path.join(temp_dir, "temp.config")
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(req.config_content)
            
        logs = []
        if req.clear_cache:
            r1 = subprocess.run(["adb", "-s", device, "shell", "pm clear com.integration.unitvsiptv"], capture_output=True, text=True, timeout=10)
            logs.append(f"Limpeza de cache com.integration.unitvsiptv: {r1.stdout.strip() or 'OK'}")
            
        subprocess.run(["adb", "-s", device, "push", temp_file, "/storage/emulated/0/Android/.config"], capture_output=True, text=True, timeout=10)
        subprocess.run(["adb", "-s", device, "push", temp_file, "/storage/emulated/0/.config"], capture_output=True, text=True, timeout=10)
        logs.append("Arquivo .config injetado em /storage/emulated/0/Android/.config")
        
        if req.launch_app:
            subprocess.run(["adb", "-s", device, "shell", "monkey -p com.integration.unitvsiptv -c android.intent.category.LAUNCHER 1"], capture_output=True, text=True, timeout=10)
            logs.append("UniTV Free iniciado no emulador!")
            
        return {
            "success": True,
            "device": device,
            "logs": logs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- SERVIR INTERFACE HTML ---

@app.get("/")
def serve_index():
    index_file = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h1>Gerador de .config</h1><p>index.html não encontrado.</p>")


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    print("=" * 60)
    print(f"🚀 Servidor do Gerador Local + Nuvem (10k) & ADB iniciado!")
    print(f"📡 Acesso Local:    http://localhost:{port}")
    print(f"🌐 Acesso na Rede:  http://{host}:{port}")
    print("=" * 60)
    uvicorn.run("server:app", host=host, port=port, reload=False)
