"""
Scanner Headless Agent (Ponte Web-ADB) - client_node.py
Micro-servidor HTTP local rodando em 127.0.0.1:21504 com FastAPI e Uvicorn
Atua como ponte entre o Painel Web (SaaS) e o Emulador Android local (ADB)
"""

import os
import sys
import re
import time
import json
import uuid
import hashlib
import threading
import subprocess
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

import generator_engine as engine

# Diretório base
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Pacotes do UniTV
UNITV_PACKAGES = ["com.integration.unitvsiptv", "com.unitv.freetv"]

# --- IDENTIFICAÇÃO DE HARDWARE (HWID) ---

def get_hwid() -> str:
    """
    Obtém um identificador único de hardware (HWID) da máquina local.
    Prioriza o UUID da placa-mãe/BIOS no Windows (PowerShell/CIM/wmic),
    machine-id no Linux ou IOPlatformUUID no macOS, com fallback para uuid.getnode().
    Retorna uma string hexadecimal de 32 caracteres (SHA-256).
    """
    try:
        if sys.platform == "win32":
            try:
                cmd = ["powershell", "-NoProfile", "-Command", "(Get-CimInstance -Class Win32_ComputerSystemProduct).UUID"]
                output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=3).decode().strip()
                if output and len(output) > 8 and "FFFFFFFF" not in output.upper():
                    return hashlib.sha256(output.encode("utf-8")).hexdigest()[:32].upper()
            except Exception:
                pass

            try:
                cmd = ["wmic", "csproduct", "get", "uuid"]
                output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=3).decode()
                lines = [l.strip() for l in output.splitlines() if l.strip() and "UUID" not in l.upper()]
                if lines and len(lines[0]) > 8:
                    return hashlib.sha256(lines[0].encode("utf-8")).hexdigest()[:32].upper()
            except Exception:
                pass

        elif sys.platform.startswith("linux"):
            for p in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
                if os.path.exists(p):
                    with open(p, "r", encoding="utf-8") as f:
                        raw = f.read().strip()
                        if raw:
                            return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32].upper()

        elif sys.platform == "darwin":
            cmd = ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"]
            output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=3).decode()
            for line in output.splitlines():
                if "IOPlatformUUID" in line:
                    parts = line.split("=")
                    if len(parts) > 1:
                        uuid_val = parts[1].strip().replace('"', '')
                        return hashlib.sha256(uuid_val.encode("utf-8")).hexdigest()[:32].upper()

    except Exception:
        pass

    node_id = str(uuid.getnode())
    return hashlib.sha256(f"HWID-FALLBACK-{node_id}".encode("utf-8")).hexdigest()[:32].upper()


# --- UTILITÁRIOS ADB ---

def get_adb_cmd() -> str:
    """Retorna o caminho do executável adb"""
    tools_adb = os.path.join(BASE_DIR, "tools", "adb.exe")
    if os.path.exists(tools_adb):
        return tools_adb
    local_adb = os.path.join(BASE_DIR, "adb.exe")
    if os.path.exists(local_adb):
        return local_adb
    import shutil
    if shutil.which("adb"):
        return "adb"
    common_adbs = [
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
    for p in common_adbs:
        if os.path.exists(p):
            return p
    return "adb"


def check_adb_status(device: str = "127.0.0.1:21503") -> bool:
    """Verifica se há dispositivo ADB conectado"""
    try:
        adb_bin = get_adb_cmd()
        subprocess.run([adb_bin, "connect", device], capture_output=True, text=True, timeout=2)
        res = subprocess.run([adb_bin, "devices"], capture_output=True, text=True, timeout=3)
        for line in res.stdout.splitlines()[1:]:
            if "\tdevice" in line:
                return True
    except Exception:
        pass
    return False


def get_adb_devices(device_addr: Optional[str] = None) -> List[str]:
    """Lista dispositivos ADB conectados"""
    try:
        adb_bin = get_adb_cmd()
        if device_addr:
            try:
                subprocess.run([adb_bin, "connect", device_addr], capture_output=True, timeout=2)
            except Exception:
                pass
        res = subprocess.run([adb_bin, "devices"], capture_output=True, text=True, timeout=3)
        devices = [line.split("\t")[0].strip() for line in res.stdout.splitlines()[1:] if "\tdevice" in line]
        if not devices:
            common_ports = [
                "127.0.0.1:21503", "127.0.0.1:21513", "127.0.0.1:21523",
                "127.0.0.1:16384", "127.0.0.1:16416", "127.0.0.1:7555",
                "127.0.0.1:5555", "127.0.0.1:5556", "127.0.0.1:62001"
            ]
            for test_addr in common_ports:
                try:
                    subprocess.run([adb_bin, "connect", test_addr], capture_output=True, timeout=1)
                except Exception:
                    pass
            res = subprocess.run([adb_bin, "devices"], capture_output=True, text=True, timeout=2)
            devices = [line.split("\t")[0].strip() for line in res.stdout.splitlines()[1:] if "\tdevice" in line]
        return devices
    except Exception:
        return []


def grant_all_app_permissions(device: str):
    """Concede todas as permissões de armazenamento, áudio, mídia e sistema no Android 6 ao 15"""
    try:
        adb_bin = get_adb_cmd()
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
        appops = [
            "MANAGE_EXTERNAL_STORAGE",
            "READ_EXTERNAL_STORAGE",
            "WRITE_EXTERNAL_STORAGE",
            "SYSTEM_ALERT_WINDOW"
        ]
        for pkg in UNITV_PACKAGES:
            for p in perms:
                subprocess.run([adb_bin, "-s", device, "shell", f"pm grant {pkg} {p}"], capture_output=True, timeout=2)
            for op in appops:
                subprocess.run([adb_bin, "-s", device, "shell", f"appops set {pkg} {op} allow"], capture_output=True, timeout=2)
    except Exception:
        pass


def deep_wipe_emulator(device: str):
    """Executa o Smart Wipe no emulador"""
    adb_bin = get_adb_cmd()
    for pkg in UNITV_PACKAGES:
        subprocess.run([adb_bin, "-s", device, "shell", f"am force-stop {pkg}"], capture_output=True, timeout=5)
    subprocess.run([adb_bin, "-s", device, "shell", "rm -rf /storage/emulated/0/Android/.config /sdcard/Android/.config /storage/emulated/0/.config /sdcard/.config /sdcard/.properties /storage/emulated/0/.properties /sdcard/cache.config.xml /storage/emulated/0/cache.config.xml /sdcard/window_dump.xml"], capture_output=True, timeout=5)
    grant_all_app_permissions(device)


def inspect_emulator_account_info(device: str, target_mac: Optional[str] = None) -> Dict[str, Any]:
    """Inspeciona a conta carregada no emulador"""
    adb_bin = get_adb_cmd()
    account_id = None
    activation_date = None
    days_active = None
    status_msg = "Desconhecido"
    is_valid = False
    final_mac = target_mac or "-"

    try:
        # Aguarda inicialização (Smart Wait)
        time.sleep(3.0)

        # Leitura do cache.config.xml em shared_prefs
        xml_stdout = ""
        for pkg in UNITV_PACKAGES:
            r_xml = subprocess.run([adb_bin, "-s", device, "shell", f"su -c 'cat /data/data/{pkg}/shared_prefs/cache.config.xml'"], capture_output=True, text=True, errors="ignore", timeout=3)
            if r_xml.stdout and "<map>" in r_xml.stdout:
                xml_stdout = r_xml.stdout
                break

        if xml_stdout:
            uid_match = re.search(r'name="key_user_id"[^>]*>([0-9]+)<', xml_stdout)
            if uid_match and uid_match.group(1).strip():
                account_id = uid_match.group(1).strip()
            
            mac_match = re.search(r'name="key_mac"[^>]*>([0-9A-Fa-f:]{17})<', xml_stdout)
            if mac_match:
                final_mac = mac_match.group(1).upper()

        user_id_int = int(account_id) if (account_id and account_id.isdigit()) else 0

        # Regra de Negócio de Validação
        if user_id_int >= 567000000:
            is_valid = True
            days_active = 0
            status_msg = "✨ 0 DIAS (VIRGEM)"
        elif user_id_int > 0:
            is_valid = False
            days_active = 0
            status_msg = f"❌ Reciclada (ID: {user_id_int} < 567M)"
        else:
            is_valid = False
            status_msg = "❌ Chute Rejeitado / EF9"

        return {
            "found": is_valid or user_id_int > 0,
            "account_id": str(user_id_int) if user_id_int > 0 else "-",
            "user_id_int": user_id_int,
            "activation_date": activation_date or datetime.now().strftime("%d-%m-%Y"),
            "days_active": days_active or 0,
            "status_message": status_msg,
            "is_valid": is_valid,
            "mac": final_mac
        }
    except Exception as e:
        return {
            "found": False,
            "account_id": "-",
            "user_id_int": 0,
            "days_active": None,
            "status_message": f"Erro: {str(e)}",
            "is_valid": False,
            "mac": final_mac
        }


# --- GERENCIADOR DO AGENTE / MOTOR DE SCANNER ---

class AgentState:
    def __init__(self):
        self.hwid = get_hwid()
        self.is_scanning = False
        self.stop_requested = False
        self.scan_thread: Optional[threading.Thread] = None

        self.current_mac = "-"
        self.current_cycle = 0
        self.total_cycles = 0
        self.active_device = "127.0.0.1:21503"
        self.master_url = os.environ.get("MASTER_URL", "http://127.0.0.1:8000")
        self.auth_token = os.environ.get("AUTH_TOKEN", None)

        self.stats = {"tested": 0, "approved": 0, "rejected": 0, "skipped": 0}
        self.recent_results: List[Dict[str, Any]] = []
        self.logs: List[str] = []
        self.lock = threading.Lock()

    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        with self.lock:
            self.logs.append(entry)
            if len(self.logs) > 100:
                self.logs.pop(0)
        print(entry)

    def to_dict(self) -> Dict[str, Any]:
        with self.lock:
            adb_ok = check_adb_status(self.active_device)
            percent = 0.0
            if self.total_cycles > 0:
                percent = round((self.current_cycle / self.total_cycles) * 100, 1)

            return {
                "status": "online",
                "service": "scanner-headless-agent",
                "version": "1.0.0",
                "hwid": self.hwid,
                "is_scanning": self.is_scanning,
                "current_mac": self.current_mac,
                "current_cycle": self.current_cycle,
                "total_cycles": self.total_cycles,
                "progress_percent": percent,
                "active_device": self.active_device,
                "adb_connected": adb_ok,
                "master_url": self.master_url,
                "stats": dict(self.stats),
                "recent_results": list(self.recent_results[-50:]),
                "recent_logs": list(self.logs[-20:])
            }


agent = AgentState()


# --- LOOP DO SCANNER (BACKGROUND THREAD) ---

def run_scanner_worker(
    base_mac: Optional[str],
    start_index: int,
    cycles: int,
    stop_on_virgin: bool,
    master_url: Optional[str],
    token: Optional[str],
    device_addr: str
):
    agent.is_scanning = True
    agent.stop_requested = False
    agent.current_cycle = 0
    agent.total_cycles = cycles
    agent.active_device = device_addr or "127.0.0.1:21503"
    if master_url:
        agent.master_url = master_url.rstrip("/")
    if token:
        agent.auth_token = token

    agent.stats = {"tested": 0, "approved": 0, "rejected": 0, "skipped": 0}
    agent.recent_results.clear()

    agent.log(f"🚀 Iniciando Scanner Headless ADB ({cycles} ciclos) em {agent.active_device}")
    adb_bin = get_adb_cmd()

    # Prepara base MAC
    clean_base = ""
    if base_mac:
        clean_base = re.sub(r'[^0-9A-Fa-f]', '', base_mac).upper()
        if clean_base.startswith("9C00D3"):
            clean_base = clean_base[6:]

    for i in range(cycles):
        if agent.stop_requested:
            agent.log("⏹️ Scanner interrompido pelo usuário.")
            break

        agent.current_cycle = i + 1
        curr_idx = start_index + i

        # Geração do MAC
        if clean_base and len(clean_base) >= 2:
            b1 = int(clean_base[0:2], 16) if len(clean_base) >= 2 else 0
            b2 = int(clean_base[2:4], 16) if len(clean_base) >= 4 else 0
            b3 = int(clean_base[4:6], 16) if len(clean_base) >= 6 else 0
            total_offset = (b1 << 16) + (b2 << 8) + b3 + i
            nb1 = (total_offset >> 16) & 0xFF
            nb2 = (total_offset >> 8) & 0xFF
            nb3 = total_offset & 0xFF
            target_mac = f"9C:00:D3:{nb1:02X}:{nb2:02X}:{nb3:02X}"
        else:
            target_mac = engine.generate_random_mac()

        agent.current_mac = target_mac
        agent.log(f"🔍 [{agent.current_cycle}/{agent.total_cycles}] Avaliando MAC: {target_mac}")

        t_start = time.time()
        auth_headers = {"Authorization": f"Bearer {agent.auth_token}"} if agent.auth_token else {}

        # 1. SMART SKIP NA NUVEM (Master API)
        smart_skipped = False
        if agent.master_url:
            try:
                chk_res = requests.get(
                    f"{agent.master_url}/api/worker/check-mac?mac={target_mac}",
                    headers=auth_headers,
                    timeout=3
                )
                if chk_res.status_code == 200:
                    chk_data = chk_res.json()
                    if chk_data.get("skip") is True:
                        smart_skipped = True
                        reason = chk_data.get("reason") or "Banido na nuvem"
                        agent.log(f"⚡ [Smart Skip] {target_mac} pulado: {reason}")
            except Exception as e:
                agent.log(f"⚠️ Erro ao consultar Smart Skip no Master: {e}")

        if smart_skipped:
            duration = round(time.time() - t_start, 1)
            item_result = {
                "index": agent.current_cycle,
                "name": f"CONFIG_{curr_idx}_{target_mac.replace(':', '')}",
                "mac": target_mac,
                "account_id": "-",
                "days_active": "-",
                "days_raw": None,
                "duration_sec": str(duration),
                "is_target": False,
                "is_valid": False,
                "status": "⚡ Smart Skip (Pulado)"
            }
            with agent.lock:
                agent.stats["skipped"] += 1
                agent.stats["tested"] += 1
                agent.recent_results.append(item_result)
            continue

        # 2. INJEÇÃO ADB LOCAL E TESTE NO EMULADOR
        try:
            temp_xml = os.path.join(BASE_DIR, "temp_agent_cache.config.xml")
            xml_text = engine.generate_xml_content(mac=target_mac)
            with open(temp_xml, "w", encoding="utf-8") as f:
                f.write(xml_text)

            # Deep wipe e injeção
            deep_wipe_emulator(agent.active_device)
            subprocess.run([adb_bin, "-s", agent.active_device, "push", temp_xml, "/sdcard/cache.config.xml"], capture_output=True, timeout=5)
            for pkg in UNITV_PACKAGES:
                subprocess.run([adb_bin, "-s", agent.active_device, "shell", f"su -c 'mkdir -p /data/data/{pkg}/shared_prefs && cp /sdcard/cache.config.xml /data/data/{pkg}/shared_prefs/cache.config.xml && chmod 666 /data/data/{pkg}/shared_prefs/cache.config.xml'"], capture_output=True, timeout=5)

            # Inicia app
            for pkg in UNITV_PACKAGES:
                subprocess.run([adb_bin, "-s", agent.active_device, "shell", f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1"], capture_output=True, timeout=5)

            # Inspeciona resultado
            info = inspect_emulator_account_info(agent.active_device, target_mac=target_mac)
            duration = round(time.time() - t_start, 1)

            acc_id = info.get("account_id") or "-"
            days_act = info.get("days_active")
            is_valid = info.get("is_valid", False)
            status_message = info.get("status_message") or ("✨ 0 DIAS (VIRGEM)" if is_valid else "❌ Inválida")

            # 3. REPORT PARA O MASTER API
            if agent.master_url:
                try:
                    report_payload = {
                        "mac_address": target_mac,
                        "account_id": acc_id if acc_id != "-" else None,
                        "days_active": days_act if isinstance(days_act, int) else None,
                        "status_message": status_message,
                        "is_valid": is_valid
                    }
                    rep_res = requests.post(
                        f"{agent.master_url}/api/worker/report",
                        json=report_payload,
                        headers=auth_headers,
                        timeout=5
                    )
                    if rep_res.status_code == 200:
                        agent.log(f"☁️ Relatório do MAC {target_mac} enviado ao Master API!")
                except Exception as e:
                    agent.log(f"⚠️ Falha ao enviar relatório ao Master: {e}")

            item_result = {
                "index": agent.current_cycle,
                "name": f"CONFIG_{curr_idx}_{target_mac.replace(':', '')}",
                "mac": target_mac,
                "account_id": acc_id,
                "days_active": f"{days_act} dias" if days_act is not None else "-",
                "days_raw": days_act,
                "duration_sec": str(duration),
                "is_target": is_valid,
                "is_valid": is_valid,
                "status": status_message
            }

            with agent.lock:
                agent.stats["tested"] += 1
                if is_valid:
                    agent.stats["approved"] += 1
                else:
                    agent.stats["rejected"] += 1
                agent.recent_results.append(item_result)

            agent.log(f"🏁 Resultado: {target_mac} -> {status_message} (ID: {acc_id}) em {duration}s")

            # Pausa se encontrar virgem/ativa
            if stop_on_virgin and is_valid:
                agent.log(f"🎯 Conta Virgem encontrada ({target_mac})! Pausando scanner conforme configurado.")
                break

        except Exception as e:
            agent.log(f"❌ Erro na execução ADB do MAC {target_mac}: {e}")
            with agent.lock:
                agent.stats["tested"] += 1
                agent.stats["rejected"] += 1

    agent.is_scanning = False
    agent.log("✨ Loop de Scanner concluído no Agente Local.")


# --- APLICAÇÃO FASTAPI (MICRO-SERVIÇO LOCAL) ---

app = FastAPI(
    title="Scanner Headless Agent (Ponte Web-ADB)",
    description="Micro-servidor local para comunicação entre o Painel Web SaaS e o Emulador ADB do cliente",
    version="1.0.0"
)

# Configuração essencial de CORS para chamadas Ajax/Fetch da aplicação Web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScanStartRequest(BaseModel):
    base_mac: Optional[str] = None
    start_index: Optional[int] = 1
    cycles: Optional[int] = 10
    stop_on_virgin: Optional[bool] = True
    master_url: Optional[str] = None
    token: Optional[str] = None
    device_addr: Optional[str] = "127.0.0.1:21503"


@app.get("/")
@app.get("/status")
def get_agent_status():
    """Retorna o status de conexão, HWID da máquina e estado atual do scanner"""
    return agent.to_dict()


@app.post("/scan/start")
def start_scan_endpoint(req: ScanStartRequest):
    """Inicia a thread do scanner local no emulador ADB"""
    if agent.is_scanning:
        return {"success": False, "message": "Scanner já em execução no Agente Local."}

    thread = threading.Thread(
        target=run_scanner_worker,
        kwargs={
            "base_mac": req.base_mac,
            "start_index": req.start_index or 1,
            "cycles": req.cycles or 10,
            "stop_on_virgin": req.stop_on_virgin if req.stop_on_virgin is not None else True,
            "master_url": req.master_url,
            "token": req.token,
            "device_addr": req.device_addr or "127.0.0.1:21503"
        },
        daemon=True
    )
    agent.scan_thread = thread
    thread.start()

    return {
        "success": True,
        "message": f"Scanner iniciado com sucesso para {req.cycles or 10} ciclos!",
        "hwid": agent.hwid
    }


@app.post("/scan/stop")
def stop_scan_endpoint():
    """Interrompe a thread de scanner em execução"""
    agent.stop_requested = True
    agent.is_scanning = False
    return {"success": True, "message": "Comando de parada enviado ao Scanner Local."}


@app.get("/scan/results")
def get_scan_results():
    """Retorna os resultados acumulados do scanner"""
    with agent.lock:
        return {
            "is_scanning": agent.is_scanning,
            "current_mac": agent.current_mac,
            "stats": dict(agent.stats),
            "results": list(agent.recent_results)
        }


@app.get("/adb/devices")
def list_local_adb_devices():
    """Lista dispositivos e emuladores ADB conectados no computador local"""
    devs = get_adb_devices(agent.active_device)
    return {
        "connected": len(devs) > 0,
        "devices": devs,
        "active_device": agent.active_device
    }


@app.post("/adb/reconnect")
def reconnect_local_adb(device_addr: Optional[str] = None):
    """Força reconexão com o emulador ADB local"""
    target = device_addr or agent.active_device or "127.0.0.1:21503"
    try:
        adb_bin = get_adb_cmd()
        subprocess.run([adb_bin, "connect", target], capture_output=True, timeout=3)
        devs = get_adb_devices(target)
        agent.active_device = target if target in devs else (devs[0] if devs else target)
        return {"success": True, "connected": len(devs) > 0, "active_device": agent.active_device}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    print(f"===========================================================")
    print(f"⚡ Scanner Headless Agent (Ponte Web-ADB)")
    print(f"🔒 Hardware ID (HWID): {agent.hwid}")
    print(f"🌐 Escutando em: http://127.0.0.1:21504")
    print(f"📡 CORS liberado para comunicação com o Painel Web SaaS")
    print(f"===========================================================")
    uvicorn.run(app, host="127.0.0.1", port=21504, log_level="info")
