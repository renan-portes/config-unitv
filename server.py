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
from datetime import datetime, timedelta
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
    version="1.3.1"
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
    base_mac: Optional[str] = None
    sequential: bool = True
    start_mac_byte: Optional[int] = None
    fresh_account: bool = True
    save_to_disk: bool = False


class DecodeRequest(BaseModel):
    hex_string: str


class SaveDiskRequest(BaseModel):
    configs: list
    target_dir: Optional[str] = "."


class ADBInjectRequest(BaseModel):
    config_content: Optional[str] = None
    xml_content: Optional[str] = None
    mac: Optional[str] = None
    device_addr: Optional[str] = "127.0.0.1:21503"
    clear_cache: bool = True
    launch_app: bool = True


# --- ROTAS DA API ---

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "config-generator", "version": "1.3.1", "mode": "local-cloud-adb"}


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
            base_mac=req.base_mac,
            sequential=req.sequential,
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
            base_mac=req.base_mac,
            sequential=req.sequential,
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
                    text = r.text
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


def get_adb_cmd() -> str:
    """Retorna o caminho do executavel adb (embutido em tools/, PATH ou emuladores comuns)"""
    tools_adb = os.path.join(BASE_DIR, "tools", "adb.exe")
    if os.path.exists(tools_adb):
        return tools_adb
    local_adb = os.path.join(BASE_DIR, "adb.exe")
    if os.path.exists(local_adb):
        return local_adb
    import shutil
    if shutil.which("adb"):
        return "adb"
    common_emu_adbs = [
        r"C:\Program Files\platform-tools\adb.exe",
        r"C:\Program Files\Microvirt\MEmu\adb.exe",
        r"C:\Program Files (x86)\Microvirt\MEmu\adb.exe",
        r"D:\Program Files\Microvirt\MEmu\adb.exe",
        r"C:\Program Files\Netease\MuMuPlayer-12.0\shell\adb.exe",
        r"C:\Program Files\Netease\MuMuPlayerGlobal-12.0\shell\adb.exe",
        r"C:\Program Files\Nox\bin\nox_adb.exe",
        r"C:\LDPlayer\LDPlayer9\adb.exe",
        r"C:\LDPlayer\LDPlayer4\adb.exe",
        r"D:\LDPlayer\LDPlayer9\adb.exe",
    ]
    for p in common_emu_adbs:
        if os.path.exists(p):
            return p
    return "adb"


def get_screen_size(device: str) -> tuple[int, int]:
    """Obtém a resolução real da tela do emulador (largura, altura)"""
    try:
        adb_bin = get_adb_cmd()
        res = subprocess.run([adb_bin, "-s", device, "shell", "wm size"], capture_output=True, text=True, errors='ignore', timeout=4)
        m = re.search(r'(?:Physical|Override)\s*size:\s*(\d+)x(\d+)', res.stdout)
        if m:
            w, h = int(m.group(1)), int(m.group(2))
            return max(w, h), min(w, h)
    except Exception:
        pass
    return 1280, 720


def ensure_adb_connected(device: Optional[str] = None):
    """Tenta conectar ao endereço do emulador se não estiver conectado"""
    global current_active_adb_device
    target = device or current_active_adb_device or "127.0.0.1:21503"
    try:
        adb_bin = get_adb_cmd()
        subprocess.run([adb_bin, "connect", target], capture_output=True, text=True, timeout=4)
        current_active_adb_device = target
    except Exception:
        pass


@app.get("/api/adb/devices")
def get_adb_devices(device_addr: Optional[str] = None):
    """Detecta emuladores e dispositivos Android conectados via ADB com auto-descoberta de portas"""
    global current_active_adb_device
    try:
        adb_bin = get_adb_cmd()
        if device_addr:
            ensure_adb_connected(device_addr)
            
        res = subprocess.run([adb_bin, "devices"], capture_output=True, text=True, timeout=5)
        devices = [line.split("\t")[0].strip() for line in res.stdout.splitlines()[1:] if "\tdevice" in line]
        
        # Se nenhum conectado, tenta portas comuns (MuMu 12/6, MEmu, LDPlayer, Nox)
        if not devices:
            common_ports = [
                "127.0.0.1:21503", "127.0.0.1:21513", "127.0.0.1:21523",
                "127.0.0.1:16384", "127.0.0.1:16416", "127.0.0.1:16448",
                "127.0.0.1:7555",
                "127.0.0.1:5555", "127.0.0.1:5556", "127.0.0.1:5558",
                "127.0.0.1:62001", "127.0.0.1:62025"
            ]
            for test_addr in common_ports:
                try:
                    subprocess.run([adb_bin, "connect", test_addr], capture_output=True, text=True, timeout=1)
                except Exception:
                    pass
            res = subprocess.run([adb_bin, "devices"], capture_output=True, text=True, timeout=3)
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
        adb_bin = get_adb_cmd()
        subprocess.run([adb_bin, "connect", device], capture_output=True, text=True, timeout=5)
        res = subprocess.run([adb_bin, "devices"], capture_output=True, text=True, timeout=5)
        devices = [line.split("\t")[0].strip() for line in res.stdout.splitlines()[1:] if "\tdevice" in line]
        if devices:
            current_active_adb_device = device if device in devices else devices[0]
        return {"success": True, "connected": len(devices) > 0, "devices": devices, "active_device": current_active_adb_device}
    except Exception as e:
        return {"success": False, "error": str(e)}


def grant_all_app_permissions(device: str):
    """Concede todas as permissões de armazenamento, áudio, mídia e sistema no Android 6 ao 15"""
    try:
        adb_bin = get_adb_cmd()
        pkg = "com.integration.unitvsiptv"
        
        # 1. Permissões de Runtime (Android 6 a 15)
        perms = [
            "android.permission.READ_EXTERNAL_STORAGE",
            "android.permission.WRITE_EXTERNAL_STORAGE",
            "android.permission.READ_MEDIA_AUDIO",
            "android.permission.READ_MEDIA_IMAGES",
            "android.permission.READ_MEDIA_VIDEO",
            "android.permission.POST_NOTIFICATIONS",
            "android.permission.READ_PHONE_STATE",
            "android.permission.ACCESS_NETWORK_STATE",
            "android.permission.ACCESS_WIFI_STATE"
        ]
        for p in perms:
            subprocess.run([adb_bin, "-s", device, "shell", f"pm grant {pkg} {p}"], capture_output=True, timeout=2)
            
        # 2. AppOps para Android 11, 12, 13, 14, 15 (Scoped Storage e Gerenciamento de Arquivos)
        appops = [
            "MANAGE_EXTERNAL_STORAGE",
            "READ_EXTERNAL_STORAGE",
            "WRITE_EXTERNAL_STORAGE",
            "READ_MEDIA_AUDIO",
            "READ_MEDIA_IMAGES",
            "READ_MEDIA_VIDEO",
            "SYSTEM_ALERT_WINDOW"
        ]
        for op in appops:
            subprocess.run([adb_bin, "-s", device, "shell", f"appops set {pkg} {op} allow"], capture_output=True, timeout=2)
    except Exception:
        pass


@app.post("/api/adb/clear-app")
def clear_app_data(req: Optional[dict] = None):
    """Limpa dados do aplicativo e configs antigas no emulador e reconcede permissões"""
    global current_active_adb_device
    device = (req or {}).get("device_addr") or current_active_adb_device or "127.0.0.1:21503"
    try:
        adb_bin = get_adb_cmd()
        ensure_adb_connected(device)
        subprocess.run([adb_bin, "-s", device, "shell", "pm clear com.integration.unitvsiptv; rm -rf /sdcard/Alarms/system_uf /sdcard/.config /sdcard/.properties /storage/emulated/0/Android/.config /storage/emulated/0/.config /sdcard/Android/.config"], capture_output=True, text=True, timeout=10)
        grant_all_app_permissions(device)
        return {"success": True, "message": "Cache e dados limpos com sucesso no emulador!"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/adb/launch-app")
def launch_app_data(req: Optional[dict] = None):
    """Inicia o UniTV Free no emulador garantindo permissões no Android 12-15"""
    global current_active_adb_device
    device = (req or {}).get("device_addr") or current_active_adb_device or "127.0.0.1:21503"
    try:
        adb_bin = get_adb_cmd()
        ensure_adb_connected(device)
        grant_all_app_permissions(device)
        subprocess.run([adb_bin, "-s", device, "shell", "monkey -p com.integration.unitvsiptv -c android.intent.category.LAUNCHER 1"], capture_output=True, text=True, timeout=10)
        return {"success": True, "message": "UniTV Free iniciado no emulador!"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_app_lifecycle_and_guide(device: str, max_wait_sec: int = 8) -> bool:
    """
    Aguarda inteligentemente o ciclo de inicialização do app com detecção precoce de erro EF9:
    - WelcomeActivity (tela de splash/carregamento) -> aguarda carregar com segurança.
    - GuidePageActivity (tela de boas-vindas/tutorial) -> avança os 2 slides com DPAD_CENTER / ENTER.
    - HomeActivity (tela principal) -> sincroniza com o servidor.
    - EF9 / Falha de Login -> interrompe imediatamente em ~2-3s para economizar tempo.
    """
    adb_bin = get_adb_cmd()
    home_reached = False
    
    for sec in range(max_wait_sec):
        res = subprocess.run([adb_bin, "-s", device, "shell", "dumpsys window | grep -E mCurrentFocus"], capture_output=True, text=True, errors='ignore', timeout=3)
        focus = res.stdout or ""
        
        # 1. Checa se o cache.config.xml já foi autenticado pelo servidor
        r_xml = subprocess.run([adb_bin, "-s", device, "shell", "su -c 'cat /data/data/com.integration.unitvsiptv/shared_prefs/cache.config.xml'"], capture_output=True, text=True, errors='ignore', timeout=2)
        xml_text = r_xml.stdout or ""
        if 'name="key_user_id"' in xml_text and '<string name="key_user_id"></string>' not in xml_text:
            m_uid = re.search(r'name="key_user_id"[^>]*>([0-9]+)<', xml_text)
            if m_uid and m_uid.group(1).strip():
                home_reached = True
                break
            
        # 2. Checa se deu erro EF9 / Falha de login
        if "EF9" in focus or "Dialog" in focus or "AlertDialog" in focus:
            break
            
        if "GuidePageActivity" in focus:
            subprocess.run([adb_bin, "-s", device, "shell", "input keyevent KEYCODE_DPAD_CENTER; input keyevent KEYCODE_ENTER"], timeout=2)
            time.sleep(0.8)
            subprocess.run([adb_bin, "-s", device, "shell", "input keyevent KEYCODE_DPAD_CENTER; input keyevent KEYCODE_ENTER"], timeout=2)
            time.sleep(1.0)
        elif "HomeActivity" in focus or "MainActivity" in focus:
            home_reached = True
            break
        elif "PermissionDialog" in focus or "GrantPermissionsActivity" in focus:
            subprocess.run([adb_bin, "-s", device, "shell", "input keyevent KEYCODE_DPAD_CENTER; input keyevent KEYCODE_ENTER"], timeout=2)
            time.sleep(0.5)
            
        time.sleep(0.8)
        
    return home_reached


def dismiss_guide_and_popups(device: str):
    """Função de compatibilidade que aciona o manipulador inteligente de ciclo de vida"""
    return handle_app_lifecycle_and_guide(device, max_wait_sec=6)


def inspect_emulator_account_info(device: str = "127.0.0.1:21503", expected_config_content: str = None) -> dict:
    """
    Lê as informações da conta (ID, data de ativação e dias ativos reais) diretamente da interface do app no emulador
    e complementa com os dados do cache.config.xml do shared_prefs.
    Salva a pasta de backup no formato exato: CONFIG_{user_id}_{days_active}DIAS
    """
    try:
        adb_bin = get_adb_cmd()
        grant_all_app_permissions(device)
        
        # 1. Leitura direta do cache.config.xml no shared_prefs
        xml_stdout = ""
        r_xml = subprocess.run([adb_bin, "-s", device, "shell", "su -c 'cat /data/data/com.integration.unitvsiptv/shared_prefs/cache.config.xml'"], capture_output=True, text=True, errors='ignore', timeout=3)
        if r_xml.stdout and "<map>" in r_xml.stdout:
            xml_stdout = r_xml.stdout
                
        account_id = None
        app_mac = None
        key_n_bt = ""
        if xml_stdout:
            m_app_mac = re.search(r'name="KEY_SP_SN"[^>]*>([^<]+)<', xml_stdout) or re.search(r'name="SP_SN_BACKUP"[^>]*>([0-9A-Fa-f:]{17})', xml_stdout)
            if m_app_mac:
                app_mac = m_app_mac.group(1).upper()
            uid_match = re.search(r'name="key_user_id"[^>]*>([0-9]+)<', xml_stdout)
            if uid_match and uid_match.group(1).strip():
                account_id = uid_match.group(1).strip()
            nbt_m = re.search(r'name="key_n_bt"[^>]*>([^<]+)<', xml_stdout)
            if nbt_m:
                key_n_bt = nbt_m.group(1)

        # Se não há key_user_id no XML, a conta foi rejeitada (EF9 / Falha no Login)
        if not account_id:
            # Fecha eventual pop-up EF9 com Back
            subprocess.run([adb_bin, "-s", device, "shell", "input keyevent KEYCODE_BACK"], timeout=2)
            return {
                "found": False,
                "account_id": "-",
                "user_id_int": 0,
                "activation_date": "-",
                "days_active": None,
                "expiration_date": "-",
                "status_message": "❌ EF9: Falha ao fazer login",
                "is_valid": False,
                "mac": app_mac or "-",
                "key_n_bt": key_n_bt,
                "folder_name": "CONFIG_INVALIDA_REPROVADA"
            }

        # 2. Inspeciona a tela de perfil para capturar os dias ativos reais
        activation_date = None
        days_active = None
        status_msg = None
        has_access_error = False
        
        try:
            # Coordenadas do ícone de perfil no canto superior direito do HomeActivity (ex: 1262, 60)
            tap_x, tap_y = 1262, 60
            subprocess.run([adb_bin, "-s", device, "shell", f"input tap {tap_x} {tap_y}"], timeout=2)
            time.sleep(1.2)
            
            dump_res = subprocess.run([adb_bin, "-s", device, "shell", "uiautomator dump /sdcard/window_dump.xml && cat /sdcard/window_dump.xml"], capture_output=True, text=True, errors='ignore', timeout=6)
            texts = re.findall(r'text="([^"]+)"', dump_res.stdout) if dump_res.stdout else []
            
            for t in texts:
                t_clean = t.strip()
                if "Falha no acesso" in t_clean or "tente novamente" in t_clean or "rejeitada" in t_clean or "EF9" in t_clean:
                    has_access_error = True
                    status_msg = t_clean
                    
                m_date = re.search(r'ativada em\s*([0-9]{2}-[0-9]{2}-[0-9]{4})', t_clean, re.IGNORECASE)
                m_days = re.search(r'([0-9]+)\s*dias', t_clean, re.IGNORECASE)
                if m_date and m_days:
                    activation_date = m_date.group(1)
                    days_active = int(m_days.group(1))
                    status_msg = t_clean
                    
                if re.match(r'^[0-9]{8,10}$', t_clean) and not account_id:
                    account_id = t_clean
                    
            # Fecha o diálogo de perfil após ler
            subprocess.run([adb_bin, "-s", device, "shell", "input keyevent KEYCODE_BACK"], timeout=2)
        except Exception:
            pass

        # 3. Validação Estrita do ID e dos Dias Ativos
        user_id_int = int(account_id) if (account_id and account_id.isdigit()) else 0
        
        if not account_id or user_id_int == 0 or has_access_error:
            # Conta inválida ou não gerada
            is_valid = False
            status_msg = status_msg or "❌ Falha no Acesso / Inválida"
            folder_name = f"CONFIG_{account_id or 'INVALIDA'}_REPROVADA"
            return {
                "found": False,
                "account_id": "-",
                "user_id_int": 0,
                "activation_date": "-",
                "days_active": None,
                "expiration_date": "-",
                "status_message": status_msg,
                "is_valid": False,
                "mac": app_mac or "-",
                "key_n_bt": key_n_bt,
                "folder_name": folder_name
            }

        # Regra de Validação key_user_id >= 567000000
        if user_id_int >= 567000000:
            is_valid = True
            if days_active is None:
                days_active = 0
            if days_active == 0:
                status_msg = "✨ 0 DIAS (VIRGEM)"
            else:
                status_msg = f"⭐ {days_active} DIAS"
        else:
            # Conta com ID menor que 567.000.000 é reciclada/antiga
            is_valid = False
            if days_active is not None:
                status_msg = f"❌ {days_active}d (< 567M Reciclada)"
            else:
                status_msg = f"❌ Reciclada (ID: {user_id_int} < 567M)"

        # Data de ativação padrão
        if not activation_date:
            activation_date = datetime.now().strftime("%d-%m-%Y")

        # Cálculo da Data de Expiração
        expiration_date = "-"
        if activation_date and days_active is not None:
            try:
                parts = activation_date.split('-')
                if len(parts) == 3:
                    d, m, y = map(int, parts)
                    dt = datetime(y, m, d) + timedelta(days=days_active)
                    expiration_date = dt.strftime("%d-%m-%Y")
            except Exception:
                pass

        # Formatação do Nome da Pasta: CONFIG_{user_id}_{days_active}DIAS
        if days_active is not None:
            folder_name = f"CONFIG_{user_id_int}_{days_active}DIAS"
        else:
            folder_name = f"CONFIG_{user_id_int}_0DIAS"
            
        if not is_valid and "REPROVADA" not in folder_name:
            folder_name += "_REPROVADA"

        # 4. Salva backup na pasta configs/CONFIG_{ID}_{XXX}DIAS/ (Apenas cache.config.xml)
        save_dir = os.path.join(BASE_DIR, "configs", folder_name)
        os.makedirs(save_dir, exist_ok=True)
        
        xml_content_to_save = xml_stdout or engine.generate_xml_content(mac=app_mac)
        with open(os.path.join(save_dir, "cache.config.xml"), "w", encoding="utf-8") as f:
            f.write(xml_content_to_save)

        return {
            "found": True,
            "account_id": str(user_id_int),
            "user_id_int": user_id_int,
            "activation_date": activation_date,
            "days_active": days_active,
            "expiration_date": expiration_date,
            "status_message": status_msg,
            "is_valid": is_valid,
            "mac": app_mac or "-",
            "key_n_bt": key_n_bt,
            "folder_name": folder_name
        }
    except Exception as e:
        return {"found": False, "error": str(e)}


@app.post("/api/adb/inject")
def inject_adb(req: ADBInjectRequest):
    """
    Injeta arquivos de configuração no emulador Android via ADB:
    1. Gera/Atualiza .config, .properties e cache.config.xml com MAC aleatório 9C:00:D3:XX:YY:ZZ
    2. Conecta ao emulador e concede permissões
    3. Copia para storage e shared_prefs
    4. Abre o app, aguarda inteligentemente o Welcome/Guide e lê as credenciais geradas
    """
    device = req.device_addr or current_active_adb_device or "127.0.0.1:21503"
    adb_bin = get_adb_cmd()
    
    try:
        temp_dir = os.path.join(BASE_DIR, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        mac = req.mac
        if not mac and req.xml_content:
            m_match = re.search(r'SP_SN_BACKUP">([0-9A-Fa-f:]{17})', req.xml_content)
            if m_match:
                mac = m_match.group(1)
        if not mac:
            mac = engine.generate_random_mac()
            
        xml_text = req.xml_content or engine.generate_xml_content(mac=mac)
        temp_xml = os.path.join(temp_dir, "cache.config.xml")
        
        with open(temp_xml, "w", encoding="utf-8") as f:
            f.write(xml_text)
            
        logs = []
        ensure_adb_connected(device)
        logs.append(f"Conectando ao dispositivo ADB: {device}")
        
        if req.clear_cache:
            subprocess.run([adb_bin, "-s", device, "shell", "pm clear com.integration.unitvsiptv; rm -rf /sdcard/Alarms/system_uf /sdcard/.config /sdcard/.properties /storage/emulated/0/Android/.config /storage/emulated/0/.config /sdcard/Android/.config /sdcard/cache.config.xml /storage/emulated/0/cache.config.xml /data/data/com.integration.unitvsiptv/shared_prefs/cache.config.xml"], capture_output=True, text=True, timeout=10)
            logs.append("Limpeza profunda de cache e storage anterior realizada com sucesso")
            grant_all_app_permissions(device)
            
        # Cria diretórios de destino se não existirem
        subprocess.run([adb_bin, "-s", device, "shell", "mkdir -p /sdcard /data/data/com.integration.unitvsiptv/shared_prefs"], capture_output=True, text=True, timeout=10)

        # Injeta exclusivamente o cache.config.xml com a tag SP_SN_BACKUP
        subprocess.run([adb_bin, "-s", device, "push", temp_xml, "/sdcard/cache.config.xml"], capture_output=True, text=True, timeout=10)
        
        # Injeta diretamente em shared_prefs com permissão 666 para o app ler
        subprocess.run([adb_bin, "-s", device, "shell", "su -c 'mkdir -p /data/data/com.integration.unitvsiptv/shared_prefs && cp /sdcard/cache.config.xml /data/data/com.integration.unitvsiptv/shared_prefs/cache.config.xml && chmod 666 /data/data/com.integration.unitvsiptv/shared_prefs/cache.config.xml'"], capture_output=True, text=True, timeout=5)
        
        logs.append(f"cache.config.xml atualizado com MAC {mac}")
        
        account_info = None
        if req.launch_app:
            if req.clear_cache:
                # Primeiro lançamento após limpeza completa
                grant_all_app_permissions(device)
                subprocess.run([adb_bin, "-s", device, "shell", "monkey -p com.integration.unitvsiptv -c android.intent.category.LAUNCHER 1"], capture_output=True, text=True, timeout=10)
                logs.append("UniTV Free iniciado no emulador (Modo Inicial)...")
                handle_app_lifecycle_and_guide(device, max_wait_sec=15)
                time.sleep(2.0)
            else:
                # Modo Rápido: Reinício expresso sem resetar dados/guia
                subprocess.run([adb_bin, "-s", device, "shell", "am force-stop com.integration.unitvsiptv"], capture_output=True, timeout=5)
                time.sleep(0.3)
                subprocess.run([adb_bin, "-s", device, "shell", "monkey -p com.integration.unitvsiptv -c android.intent.category.LAUNCHER 1"], capture_output=True, timeout=5)
                logs.append("UniTV Free reiniciado expressamente (Modo Rápido)...")
                handle_app_lifecycle_and_guide(device, max_wait_sec=12)
                time.sleep(1.2)
            
            logs.append("Lendo status e credenciais diretamente do aplicativo...")
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
