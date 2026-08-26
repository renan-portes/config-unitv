"""
Servidor Web e API REST para o Gerador de Configurações IPTV
Suporta geração local de novas contas, injeção ADB no emulador e integração com o Pool da Nuvem (10.231 configs)
"""

import os
import io
import re
import time
import json
import base64
import random
import subprocess
import requests
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
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

import sys
import webbrowser
import threading

if getattr(sys, 'frozen', False):
    BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CLOUD_IDS_URL = "https://raw.githubusercontent.com/iurysouza041095-bit/sorteio/main/ids.json"
cached_cloud_ids = []

apps_dir = os.path.join(BASE_DIR, "apps")
if os.path.exists(apps_dir):
    app.mount("/apps", StaticFiles(directory=apps_dir), name="apps")


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

def load_cloud_ids() -> list:
    """Carrega a lista de IDs localmente de ids.json ou faz fallback para URL remota"""
    local_file = os.path.join(BASE_DIR, "ids.json")
    if os.path.exists(local_file):
        try:
            with open(local_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                ids = data.get("arquivos", [])
                if ids:
                    return ids
        except Exception as e:
            print(f"Aviso ao ler ids.json local: {e}")
            
    try:
        r = requests.get(CLOUD_IDS_URL, timeout=10)
        return r.json().get("arquivos", [])
    except Exception as e:
        print(f"Aviso ao buscar ids remotos: {e}")
        return []


@app.get("/api/cloud/random")
def get_random_cloud_config():
    """Puxa uma configuração fresca aleatória do pool da nuvem (10.231 disponíveis)"""
    global cached_cloud_ids
    try:
        if not cached_cloud_ids:
            cached_cloud_ids = load_cloud_ids()
            
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


@app.get("/api/cloud/batch")
def get_batch_cloud_configs(count: int = 10):
    """Retorna múltiplas configurações da nuvem em paralelo super rápido"""
    try:
        ids = load_cloud_ids()
        if not ids:
            raise HTTPException(status_code=500, detail="Pool de IDs da nuvem vazio ou indisponível")
            
        chosen_ids = random.sample(ids, min(count, len(ids), 50))
        
        def fetch_one(id_str):
            try:
                url = f"https://drive.google.com/uc?export=download&id={id_str}"
                r = requests.get(url, timeout=6)
                if r.ok and "key_device_id_unitvfree" in r.text:
                    mac_m = re.search(r'(?:KEY_SP_SN|key_mac|mac)=([^\s\r\n]+)', text) or re.search(r'([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})', text)
                    mac = mac_m.group(1).upper() if mac_m else engine.generate_smart_random_mac()
                    return {
                        "id": id_str,
                        "mac": mac,
                        "config": text
                    }
            except Exception:
                pass
            return None

        with ThreadPoolExecutor(max_workers=min(count, 15)) as executor:
            results = list(executor.map(fetch_one, chosen_ids))

        valid_results = [res for res in results if res is not None]
        return {
            "count": len(valid_results),
            "total_available": len(ids),
            "items": valid_results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar lote na nuvem: {str(e)}")


# --- ENDPOINTS ADB (EMULADOR) ---

current_active_adb_device = "127.0.0.1:21503"


def ensure_adb_connected(device: Optional[str] = None):
    """Tenta conectar ao endereço do emulador se não estiver conectado"""
    global current_active_adb_device
    target = device or current_active_adb_device or "127.0.0.1:21503"
    try:
        subprocess.run(["adb", "connect", target], capture_output=True, text=True, timeout=4)
        current_active_adb_device = target
    except Exception:
        pass


@app.get("/api/adb/devices")
def get_adb_devices(device_addr: Optional[str] = None):
    """Detecta emuladores e dispositivos Android conectados via ADB com auto-descoberta de portas"""
    global current_active_adb_device
    try:
        if device_addr:
            ensure_adb_connected(device_addr)
            
        res = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
        devices = [line.split("\t")[0].strip() for line in res.stdout.splitlines()[1:] if "\tdevice" in line]
        
        # Se nenhum conectado, tenta portas comuns (MEmu primário/secundário, LDPlayer, Nox)
        if not devices:
            for test_addr in ["127.0.0.1:21503", "127.0.0.1:21513", "127.0.0.1:21523", "127.0.0.1:5555", "127.0.0.1:62001"]:
                try:
                    subprocess.run(["adb", "connect", test_addr], capture_output=True, text=True, timeout=1.5)
                except Exception:
                    pass
            res = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=3)
            devices = [line.split("\t")[0].strip() for line in res.stdout.splitlines()[1:] if "\tdevice" in line]
            
        if devices:
            if current_active_adb_device not in devices:
                current_active_adb_device = devices[0]
                
        return {
            "connected": len(devices) > 0,
            "devices": devices if devices else [],
            "active_device": current_active_adb_device
        }
    except Exception as e:
        return {"connected": False, "devices": [], "error": str(e)}


@app.post("/api/adb/reconnect")
def reconnect_adb(req: Optional[dict] = None):
    """Força reconexão com o dispositivo ADB especificado"""
    global current_active_adb_device
    device = (req or {}).get("device_addr") or current_active_adb_device or "127.0.0.1:21503"
    try:
        subprocess.run(["adb", "connect", device], capture_output=True, text=True, timeout=5)
        res = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
        devices = [line.split("\t")[0].strip() for line in res.stdout.splitlines()[1:] if "\tdevice" in line]
        if devices:
            current_active_adb_device = device if device in devices else devices[0]
        return {"success": True, "connected": len(devices) > 0, "devices": devices, "active_device": current_active_adb_device}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/adb/clear-app")
def clear_app_data(req: Optional[dict] = None):
    """Limpa dados do aplicativo e configs antigas no emulador"""
    global current_active_adb_device
    device = (req or {}).get("device_addr") or current_active_adb_device or "127.0.0.1:21503"
    try:
        ensure_adb_connected(device)
        subprocess.run(["adb", "-s", device, "shell", "pm clear com.integration.unitvsiptv; rm -rf /sdcard/Alarms/system_uf /sdcard/.config /sdcard/.properties /storage/emulated/0/Android/.config /storage/emulated/0/.config /sdcard/Android/.config"], capture_output=True, text=True, timeout=10)
        return {"success": True, "message": "Cache e dados limpos com sucesso no emulador!"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/adb/launch-app")
def launch_app_data(req: Optional[dict] = None):
    """Inicia o UniTV Free no emulador"""
    global current_active_adb_device
    device = (req or {}).get("device_addr") or current_active_adb_device or "127.0.0.1:21503"
    try:
        ensure_adb_connected(device)
        subprocess.run(["adb", "-s", device, "shell", "monkey -p com.integration.unitvsiptv -c android.intent.category.LAUNCHER 1"], capture_output=True, text=True, timeout=10)
        return {"success": True, "message": "UniTV Free iniciado no emulador!"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def inspect_emulator_account_info(device: str = "127.0.0.1:21503", expected_config_content: str = None) -> dict:
    """Lê as informações da conta (ID, data de ativação e dias ativos) diretamente do aplicativo no emulador com validação de MAC"""
    try:
        # 1. Passa tela de guia se estiver aberta
        focus_res = subprocess.run(["adb", "-s", device, "shell", "dumpsys window | grep -E 'mCurrentFocus'"], capture_output=True, text=True, errors='ignore', timeout=5)
        if "GuidePageActivity" in focus_res.stdout:
            subprocess.run(["adb", "-s", device, "shell", "input keyevent KEYCODE_DPAD_CENTER"], timeout=3)
            time.sleep(0.4)
            subprocess.run(["adb", "-s", device, "shell", "input keyevent KEYCODE_DPAD_RIGHT"], timeout=3)
            time.sleep(0.4)
            subprocess.run(["adb", "-s", device, "shell", "input keyevent KEYCODE_DPAD_CENTER"], timeout=3)
            time.sleep(1.5)
            
        # 2. Fecha overlays com Back
        subprocess.run(["adb", "-s", device, "shell", "input keyevent KEYCODE_BACK"], timeout=3)
        time.sleep(0.5)
        
        # 3. Abre o diálogo de perfil clicando no ícone mIvPersonal (x=1262, y=60)
        subprocess.run(["adb", "-s", device, "shell", "input tap 1262 60"], timeout=3)
        time.sleep(1.5)
        
        # 4. Dump da hierarquia da tela
        subprocess.run(["adb", "-s", device, "shell", "uiautomator dump /sdcard/window_dump.xml"], capture_output=True, timeout=5)
        dump_res = subprocess.run(["adb", "-s", device, "shell", "cat /sdcard/window_dump.xml"], capture_output=True, text=True, errors='ignore', timeout=5)
        
        texts = re.findall(r'text="([^"]+)"', dump_res.stdout)
        
        account_id = None
        activation_date = None
        days_active = None
        status_msg = None
        is_valid = True
        
        for t in texts:
            t_clean = t.strip()
            if "Falha no acesso" in t_clean or "tente novamente" in t_clean:
                is_valid = False
                status_msg = t_clean
                
            m_date = re.search(r'ativada em\s*([0-9]{2}-[0-9]{2}-[0-9]{4})', t_clean, re.IGNORECASE)
            m_days = re.search(r'([0-9]+)\s*dias', t_clean, re.IGNORECASE)
            if m_date and m_days:
                activation_date = m_date.group(1)
                days_active = int(m_days.group(1))
                status_msg = t_clean
                is_valid = True
                
            if re.match(r'^[0-9]{8,10}$', t_clean) and not account_id:
                account_id = t_clean
                
        # Leitura do cache.config.xml do app para checar MAC real carregado
        r_xml = subprocess.run(["adb", "-s", device, "shell", "su -c 'cat /data/data/com.integration.unitvsiptv/shared_prefs/cache.config.xml'"], capture_output=True, text=True, errors='ignore', timeout=5)
        app_mac = None
        m_app_mac = re.search(r'name="KEY_SP_SN">([^<]+)<', r_xml.stdout)
        if m_app_mac:
            app_mac = m_app_mac.group(1).upper()

        if not account_id:
            uid_match = re.search(r'name="key_user_id">([0-9]+)<', r_xml.stdout)
            if uid_match:
                account_id = uid_match.group(1)
                
        # Validação: Se o app rejeitou o chute e usou outra conta de fallback
        if expected_config_content:
            exp_mac_m = re.search(r'([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})', expected_config_content) or re.search(r'KEY_SP_SN=([^\s\r\n]+)', expected_config_content)
            if exp_mac_m:
                exp_mac = exp_mac_m.group(1).upper().replace(":", "")
                app_mac_clean = (app_mac or "").replace(":", "")
                if app_mac_clean and exp_mac != app_mac_clean:
                    # Verifica se o byte final coincide (decodificador nativo UniTV mapeia o byte final em 9C00D3ECAA)
                    if exp_mac[-2:] == app_mac_clean[-2:] and app_mac_clean.startswith("9C00D3ECAA"):
                        pass
                    else:
                        is_valid = False
                        status_msg = "Configuração rejeitada pelo app (Chute/Token Inválido)"
                        account_id = "-"
                        activation_date = "-"
                        days_active = None

        # Fecha o diálogo de perfil
        subprocess.run(["adb", "-s", device, "shell", "input keyevent KEYCODE_BACK"], timeout=3)
        
        return {
            "found": bool(account_id or activation_date or status_msg),
            "account_id": account_id if is_valid else "-",
            "activation_date": activation_date if is_valid else "-",
            "days_active": days_active,
            "status_message": status_msg,
            "is_valid": is_valid,
            "app_mac": app_mac
        }
    except Exception as e:
        return {"found": False, "error": str(e)}


@app.post("/api/adb/inject")
def inject_adb(req: ADBInjectRequest):
    """Injeta a .config diretamente no emulador via ADB e inicia o UniTV Free"""
    global current_active_adb_device
    try:
        device = req.device_addr or current_active_adb_device or "127.0.0.1:21503"
        temp_dir = os.path.join(BASE_DIR, ".temp")
        os.makedirs(temp_dir, exist_ok=True)
        temp_file = os.path.join(temp_dir, "temp.config")
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(req.config_content)
            
        logs = []
        ensure_adb_connected(device)
        logs.append(f"Conectando ao dispositivo ADB: {device}")
        
        if req.clear_cache:
            subprocess.run(["adb", "-s", device, "shell", "pm clear com.integration.unitvsiptv; rm -rf /sdcard/Alarms/system_uf /sdcard/.config /sdcard/.properties /storage/emulated/0/Android/.config /storage/emulated/0/.config /sdcard/Android/.config"], capture_output=True, text=True, timeout=10)
            logs.append("Limpeza profunda de cache e storage anterior realizada com sucesso")
            
        # Cria diretórios de destino se não existirem
        subprocess.run(["adb", "-s", device, "shell", "mkdir -p /storage/emulated/0/Android /sdcard/Android"], capture_output=True, text=True, timeout=10)

        # Injeta nos caminhos padrões do UniTV
        r_push1 = subprocess.run(["adb", "-s", device, "push", temp_file, "/storage/emulated/0/Android/.config"], capture_output=True, text=True, timeout=10)
        subprocess.run(["adb", "-s", device, "push", temp_file, "/storage/emulated/0/.config"], capture_output=True, text=True, timeout=10)
        subprocess.run(["adb", "-s", device, "push", temp_file, "/sdcard/Android/.config"], capture_output=True, text=True, timeout=10)
        
        logs.append("Arquivo .config injetado em /storage/emulated/0/Android/.config")
        
        account_info = None
        if req.launch_app:
            subprocess.run(["adb", "-s", device, "shell", "monkey -p com.integration.unitvsiptv -c android.intent.category.LAUNCHER 1"], capture_output=True, text=True, timeout=10)
            logs.append("UniTV Free iniciado no emulador!")
            
            # Aguarda a inicialização do app para leitura de status
            time.sleep(6)
            logs.append("Lendo status e dias ativos da conta no aplicativo...")
            account_info = inspect_emulator_account_info(device, expected_config_content=req.config_content)
            
            if account_info and account_info.get("found"):
                if account_info.get("account_id"):
                    logs.append(f"👑 ID da Conta: {account_info['account_id']}")
                if account_info.get("activation_date"):
                    logs.append(f"📅 Ativada em: {account_info['activation_date']} ({account_info.get('days_active', 0)} dias ativa)")
                if account_info.get("status_message"):
                    logs.append(f"💬 Status: {account_info['status_message']}")
            
        return {
            "success": True,
            "device": device,
            "logs": logs,
            "account_info": account_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/adb/account-info")
@app.post("/api/adb/account-info")
def get_account_info_endpoint(device_addr: Optional[str] = "127.0.0.1:21503"):
    """Endpoint para ler sob demanda os dados e dias ativos da conta no emulador"""
    return inspect_emulator_account_info(device_addr or "127.0.0.1:21503")


# --- SERVIR INTERFACE HTML & ASSETS ---

@app.get("/")
def serve_index():
    index_file = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h1>Gerador de .config</h1><p>index.html não encontrado.</p>")


@app.get("/logo.png")
def serve_logo():
    logo_file = os.path.join(BASE_DIR, "logo.png")
    if os.path.exists(logo_file):
        return FileResponse(logo_file, media_type="image/png")
    raise HTTPException(status_code=404, detail="Logo não encontrado")


@app.get("/favicon.ico")
def serve_favicon():
    logo_file = os.path.join(BASE_DIR, "logo.png")
    if os.path.exists(logo_file):
        return FileResponse(logo_file, media_type="image/png")
    raise HTTPException(status_code=404, detail="Favicon não encontrado")


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    print("=" * 60)
    print(f"🚀 Servidor do Gerador Local + Nuvem (10k) & ADB iniciado!")
    print(f"📡 Acesso Local:    http://localhost:{port}")
    print(f"🌐 Acesso na Rede:  http://{host}:{port}")
    print("=" * 60)

    def open_browser():
        time.sleep(1.2)
        try:
            webbrowser.open(f"http://localhost:{port}")
        except Exception:
            pass

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host=host, port=port, reload=False)
