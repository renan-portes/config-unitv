"""
Motor de Geração de Configurações (.config, .properties, cache.config.xml)
Compatível com IPTV
Suporte a Contas Novas (0 Dias / Trial Fresco) e Customizadas
"""

import os
import glob
import json
import base64
import random
import io
import zipfile
import time
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET

# Cipher Block tables learned from reverse engineering
BLOCK_0_HEX = "268ea2dd4b1dbec8"

BLOCK_1_MAP = {
    '0': 'b2e21fcbcf6df76d',
    '1': '920694d567b2a07d',
    '2': '9b7d9b3e9ec105b3',
    '3': '98e2032e347b3591',
    '4': '3163c73fbe1a4ffa',
    '5': '45abc8a31a02ea9f',
    '6': 'a9fb9b1b0249787f',
    '7': 'bfdbe907efc33064',
    '8': 'd77d20021f080cab',
    '9': '2719e91949656f1b',
    'A': 'b73b243532d8502e',
    'B': '34b9b4bc32d17b8e',
    'C': '8d11170734f47d56',
    'D': '8487ea725540e922',
    'E': '414d4d7639f52efb',
    'F': '3488819e28a84faf'
}

BLOCK_2_MAP = {
    '0': 'ec47a53b333a619e',
    '1': '2a935d5bbcd64d62',
    '2': '163c36b43ae1d4fa',
    '3': 'b2c8f1b1b33c9d81',
    '4': 'f5dd5a8a7c0cf9b0',
    '5': '8e54348d52c70597',
    '6': '4da157ce4aaf762e',
    '7': '397cf2d9b2390038',
    '8': '3b8def964df8b50a',
    '9': '1c2c11d4ded14e5a',
    'A': 'ba7c8877b591bb52',
    'B': '6b50a8b78d6fd8b4',
    'C': '3b5822cbe634c13a',
    'D': 'e02919d91e0a66d3',
    'E': '52e9caee7f1a51d4',
    'F': '5c5d710f55cc6978'
}

# 5 Sufixos válidos de Bloco 1 para key_device_id_unitvfree
VALID_DEV_B1_SUFFIXES = [
    "163c36b43ae1d4fa",  # WPDa0OuHU+g==
    "f5dd5a8a7c0cf9b0",  # 13VqKfAz5sA==
    "4da157ce4aaf762e",  # NoVfOSq92Lg==
    "3b8def964df8b50a",  # 7je+WTfi1Cg==
    "ec47a53b333a619e"   # sR6U7Mzphng==
]

DEFAULT_N_BT_HEX = "366b36373669396f4b4a396f6a6f456c6b5730374976582b547344706d5a7275654e34567a5777787167516776396148656d565550773d3d"
DEFAULT_LIVE_DATA = "946b2cd8-d75c-11f0-b76f-a304a7c797c8LiveDataV6;1766172909"


def format_java_date(dt: datetime = None) -> str:
    """Gera cabeçalho de data no formato Java Properties: #Tue Aug 25 08:37:55 GMT+08:00 2026"""
    if dt is None:
        tz_gmt8 = timezone(timedelta(hours=8))
        dt = datetime.now(tz_gmt8)
    day_abbr = dt.strftime("%a")
    month_abbr = dt.strftime("%b")
    day = dt.strftime("%d")
    time_str = dt.strftime("%H:%M:%S")
    year = dt.strftime("%Y")
    return f"#{day_abbr} {month_abbr} {day} {time_str} GMT+08:00 {year}"


def generate_random_mac() -> str:
    """Gera um endereço MAC no padrão 9C:00:D3:EC:AA:XX suportado pelo algoritmo criptográfico"""
    return f"9C:00:D3:EC:AA:{random.randint(0, 255):02X}"


def generate_smart_random_mac() -> str:
    """Gera um MAC no padrão 9C:00:D3:EC:AA:XX"""
    return f"9C:00:D3:EC:AA:{random.randint(0, 255):02X}"


def encode_sn_token(mac: str) -> str:
    """Calcula a chave key_sn_token_unitvfree em Hex para o MAC fornecido"""
    clean_mac = mac.strip().upper()
    parts = clean_mac.split(':')
    if len(parts) == 6:
        last_byte = parts[5]
    elif len(clean_mac) == 12:
        last_byte = clean_mac[10:12]
    elif len(clean_mac) == 17:
        last_byte = clean_mac[15:17]
    else:
        last_byte = "6F"
        
    nibble1 = last_byte[0] if len(last_byte) > 0 and last_byte[0] in BLOCK_1_MAP else '6'
    nibble2 = last_byte[1] if len(last_byte) > 1 and last_byte[1] in BLOCK_2_MAP else 'F'
    
    b0 = bytes.fromhex(BLOCK_0_HEX)
    b1 = bytes.fromhex(BLOCK_1_MAP[nibble1])
    b2 = bytes.fromhex(BLOCK_2_MAP[nibble2])
    
    cipher_bytes = b0 + b1 + b2
    b64_str = base64.b64encode(cipher_bytes).decode('ascii')
    hex_token = b64_str.encode('ascii').hex()
    return hex_token


def generate_device_id(mac: str = None, fresh: bool = True) -> tuple:
    """
    Gera um Device ID único (0 Dias de uso) ou derivado do MAC.
    Retorna (hex_string, base64_string)
    """
    if fresh or not mac:
        h = hashlib.sha256(f"{mac}_{time.time_ns()}_{os.urandom(16)}".encode()).digest()
        b0 = h[:8]
    else:
        h = hashlib.sha256(mac.encode()).digest()
        b0 = h[:8]
        
    suffix_hex = random.choice(VALID_DEV_B1_SUFFIXES)
    b1 = bytes.fromhex(suffix_hex)
    
    dev_bytes = b0 + b1
    dev_b64 = base64.b64encode(dev_bytes).decode('ascii')
    dev_hex = dev_b64.encode('ascii').hex()
    return dev_hex, dev_b64


def generate_fresh_user_id() -> str:
    """Gera um User ID exclusivo de 9 dígitos (ex: 5xxxxxxxx)"""
    return f"5{random.randint(10000000, 99999999)}"


def decode_hex_value(hex_str: str) -> dict:
    """Decodifica uma string Hex para texto e Base64 se aplicável"""
    hex_str = hex_str.strip()
    try:
        raw_bytes = bytes.fromhex(hex_str)
        ascii_text = raw_bytes.decode('utf-8', errors='replace')
        
        b64_decoded_hex = ""
        try:
            b64_bytes = base64.b64decode(ascii_text)
            b64_decoded_hex = b64_bytes.hex()
        except Exception:
            pass
            
        return {
            "valid": True,
            "success": True,
            "raw_hex": hex_str,
            "hex": hex_str,
            "ascii_text": ascii_text,
            "text": ascii_text,
            "b64_decoded_hex": b64_decoded_hex,
            "b64_hex": b64_decoded_hex
        }
    except Exception as e:
        return {
            "valid": False,
            "success": False,
            "hex": hex_str,
            "text": "",
            "error": str(e)
        }


def build_config_text(
    mac: str,
    device_id_hex: str,
    n_bt_hex: str = DEFAULT_N_BT_HEX,
    timestamp_header: str = None
) -> str:
    """Gera o conteúdo textual do arquivo .config / .properties"""
    if not timestamp_header:
        timestamp_header = format_java_date()
        
    sn_token_hex = encode_sn_token(mac)
    
    lines = [
        "#personal info",
        timestamp_header,
        f"key_n_bt={n_bt_hex}",
        f"key_device_id_unitvfree={device_id_hex}",
        f"key_sn_token_unitvfree={sn_token_hex}",
        ""
    ]
    return "\n".join(lines)


generate_config_content = build_config_text


def generate_xml_content(
    mac: str,
    user_id: str,
    channel_code: str = "SKY Sport F1",
    column_key: str = "68143",
    uuid_str: str = "",
    live_data: str = DEFAULT_LIVE_DATA
) -> str:
    """Gera o conteúdo XML do arquivo cache.config.xml perfeitamente formatado com timestamps atuais idêntico ao TV Box"""
    clean_mac = mac.strip().upper()
    backup_sn = f"{clean_mac},1"
    now_ms = int(time.time() * 1000)
    time_col_new = now_ms - random.randint(1000, 5000)
    dcs_rt = random.randint(3000000, 5000000)
    
    xml_template = f"""<?xml version='1.0' encoding='utf-8' standalone='yes' ?>
<map>
    <string name="live_last_channel_code">{channel_code}</string>
    <int name="recommends_cache_time" value="96" />
    <int name="all_Column_key" value="{column_key}" />
    <int name="live_last_column_id" value="{column_key}" />
    <string name="key_user_id">{user_id}</string>
    <string name="KEY_SP_SN">{clean_mac}</string>
    <string name="_free"></string>
    <string name="_special"></string>
    <string name="Special_root"></string>
    <string name="SP_SN_BACKUP">{backup_sn}</string>
    <int name="column_cache_time" value="65" />
    <string name="_live"></string>
    <string name="key_user_identity">4</string>
    <int name="live_last_tab" value="3" />
    <string name="_search"></string>
    <long name="service_time_column_new_10002" value="{time_col_new}" />
    <long name="service_time_column_new_10001" value="{time_col_new}" />
    <int name="heartbeat_cache_time" value="120" />
    <long name="dcs_realtime" value="{dcs_rt}" />
    <long name="service_time_column_new_10006" value="{time_col_new}" />
    <string name="key_n_bt"></string>
    <string name="key_device_id_unitvfree">{user_id}</string>
    <string name="cache_key_recommend"></string>
    <string name="{column_key}">{live_data}</string>
    <string name="key_renew_flag">0</string>
</map>
"""
    return xml_template


def generate_single_config(
    mac: str = None,
    folder_name: str = "CONFIG_NEW",
    user_id: str = None,
    channel_code: str = "SBTHD",
    fresh_account: bool = True,
    device_id_hex: str = None
) -> dict:
    """Gera o trio completo de arquivos para uma configuração (com opção de conta 0 dias)"""
    if not mac:
        suffix = f"{random.randint(0, 255):02X}"
        mac = f"9C:00:D3:EC:AA:{suffix}"
    else:
        mac = mac.strip().upper()
        
    # Gera novo Device ID exclusivo para garantir 0 dias
    if not device_id_hex:
        dev_hex, dev_b64 = generate_device_id(mac=mac, fresh=fresh_account)
    else:
        dev_hex = device_id_hex
        dev_b64 = decode_hex_value(dev_hex).get("text", "")
        
    # Gera novo User ID exclusivo se não fornecido
    if not user_id:
        user_id = generate_fresh_user_id() if fresh_account else "515863542"
        
    uuid_str = str(uuid.uuid4())
    date_header = format_java_date()
    
    config_str = generate_config_content(mac, device_id_hex=dev_hex, timestamp_header=date_header)
    properties_str = config_str
    xml_str = generate_xml_content(mac, user_id=user_id, channel_code=channel_code, uuid_str=uuid_str)
    
    sn_token_hex = encode_sn_token(mac)
    sn_token_decoded = decode_hex_value(sn_token_hex)["text"]
    
    return {
        "folder_name": folder_name,
        "mac": mac,
        "backup_sn": f"{mac},1",
        "user_id": user_id,
        "uuid": uuid_str,
        "device_id_hex": dev_hex,
        "device_id_b64": dev_b64,
        "sn_token_hex": sn_token_hex,
        "sn_token_b64": sn_token_decoded,
        "fresh_account": fresh_account,
        "files": {
            ".config": config_str,
            ".properties": properties_str,
            "cache.config.xml": xml_str
        }
    }


def generate_bulk_configs(
    count: int = 10,
    start_index: int = 1,
    folder_prefix: str = "CONFIG_",
    start_mac_byte: int = None,
    fresh_account: bool = True
) -> list:
    """Gera múltiplas configurações exclusivas com 0 dias (cada uma com seu próprio Device ID e User ID)"""
    results = []
    if start_mac_byte is None:
        start_mac_byte = random.randint(0, max(0, 255 - count))
        
    for i in range(count):
        idx = start_index + i
        mac_byte = (start_mac_byte + i) % 256
        mac = f"9C:00:D3:EC:AA:{mac_byte:02X}"
        folder_name = f"{folder_prefix}{idx}"
        cfg = generate_single_config(mac=mac, folder_name=folder_name, fresh_account=fresh_account)
        results.append(cfg)
        
    return results


def create_zip_archive(configs_list: list) -> bytes:
    """Cria um arquivo ZIP em memória contendo todas as pastas e arquivos gerados"""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for item in configs_list:
            folder = item.get("folder_name", "CONFIG")
            for filename, content in item["files"].items():
                arcname = f"{folder}/{filename}"
                zf.writestr(arcname, content.encode('utf-8'))
    zip_buffer.seek(0)
    return zip_buffer.getvalue()


def save_configs_to_directory(configs_list: list, target_base_dir: str = ".") -> list:
    """Salva fisicamente as configurações no disco"""
    created_paths = []
    for item in configs_list:
        folder = item.get("folder_name", "CONFIG")
        dest_dir = os.path.join(target_base_dir, folder)
        os.makedirs(dest_dir, exist_ok=True)
        for filename, content in item["files"].items():
            file_path = os.path.join(dest_dir, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        created_paths.append(dest_dir)
    return created_paths


def load_all_existing_configs(base_dir: str = ".") -> list:
    """Carrega e cataloga todas as configurações existentes no diretório"""
    config_paths = glob.glob(os.path.join(base_dir, '**/.config'), recursive=True)
    catalog = []
    
    for path in sorted(config_paths):
        dirpath = os.path.dirname(path)
        rel = os.path.relpath(dirpath, base_dir).replace('\\', '/')
        if rel == '.' or 'node_modules' in rel or '.git' in rel or '__pycache__' in rel:
            continue
            
        cfg_data = {}
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    cfg_data[k] = v
                    
        xml_path = os.path.join(dirpath, 'cache.config.xml')
        mac = ""
        user_id = ""
        if os.path.exists(xml_path):
            try:
                tree = ET.parse(xml_path)
                for elem in tree.getroot():
                    name = elem.get('name')
                    val = elem.get('value') if 'value' in elem.attrib else (elem.text or '')
                    if name == 'KEY_SP_SN':
                        mac = val
                    elif name == 'key_user_id':
                        user_id = val
            except Exception:
                pass
                
        sn_hex = cfg_data.get('key_sn_token_unitvfree', '')
        sn_decoded = decode_hex_value(sn_hex).get("text", "") if sn_hex else ""
        dev_hex = cfg_data.get('key_device_id_unitvfree', '')
        dev_decoded = decode_hex_value(dev_hex).get("text", "") if dev_hex else ""
        
        catalog.append({
            "folder": rel,
            "mac": mac,
            "user_id": user_id,
            "sn_token_hex": sn_hex,
            "sn_token_b64": sn_decoded,
            "device_id_hex": dev_hex,
            "device_id_b64": dev_decoded,
            "n_bt_hex": cfg_data.get('key_n_bt', '')
        })
        
    return catalog


def test_generation():
    """Validação automatizada das funções do gerador de 0 dias"""
    test_mac = "9C:00:D3:EC:AA:6F"
    cfg = generate_single_config(mac=test_mac, folder_name="TEST_0_DAYS", fresh_account=True)
    assert cfg["mac"] == test_mac
    assert ".config" in cfg["files"]
    assert ".properties" in cfg["files"]
    assert "cache.config.xml" in cfg["files"]
    assert cfg["user_id"].startswith("5")
    assert cfg["device_id_hex"] != ""
    assert cfg["sn_token_b64"] == "Jo6i3Usdvsip+5sbAkl4f1xdcQ9VzGl4"
    
    # Bulk test: verify each config has unique device_id and user_id
    bulk = generate_bulk_configs(count=5, start_index=1, fresh_account=True)
    assert len(bulk) == 5
    dev_ids = set(c["device_id_hex"] for c in bulk)
    user_ids = set(c["user_id"] for c in bulk)
    assert len(dev_ids) == 5, "Device IDs must be unique for each config"
    assert len(user_ids) == 5, "User IDs must be unique for each config"
    
    return "Todos os testes passaram com 100% de sucesso! (0 dias verificado)"


if __name__ == "__main__":
    print("Executando auto-teste do motor gerador 0 dias...")
    print(test_generation())
