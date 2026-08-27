"""
Motor de Geração de Configurações (cache.config.xml)
Compatível com IPTV / UniTV
Padrão estrito: Apenas cache.config.xml (sem .config, sem .properties)
Prefixo fixo: 9C:00:D3:
Formato obrigatório: 9C:00:D3:XX:YY:ZZ (17 caracteres, 6 partes)
"""

import os
import re
import glob
import json
import random
import io
import zipfile
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET


def generate_random_mac() -> str:
    """Gera um endereço MAC no padrão 9C:00:D3:XX:YY:ZZ (prefixo 9C:00:D3: fixo)"""
    b1 = random.randint(0, 255)
    b2 = random.randint(0, 255)
    b3 = random.randint(0, 255)
    return f"9C:00:D3:{b1:02X}:{b2:02X}:{b3:02X}"


def generate_smart_random_mac() -> str:
    """Gera um MAC no padrão 9C:00:D3:XX:YY:ZZ (prefixo 9C:00:D3: fixo)"""
    return generate_random_mac()


def normalize_or_generate_mac(user_input: str = None) -> str:
    """
    Normaliza a entrada do usuário para garantir um MAC de 6 partes e 17 caracteres (9C:00:D3:XX:YY:ZZ).
    Se incompleto (ex: F2:72), completa os octetos que faltarem.
    """
    if not user_input:
        return generate_random_mac()
        
    clean = re.sub(r'[^0-9A-Fa-f]', '', str(user_input)).upper()
    if clean.startswith("9C00D3"):
        clean = clean[6:]
        
    if len(clean) >= 6:
        b1 = clean[0:2]
        b2 = clean[2:4]
        b3 = clean[4:6]
    elif len(clean) >= 4:
        b1 = clean[0:2]
        b2 = clean[2:4]
        b3 = f"{random.randint(0, 255):02X}"
    elif len(clean) >= 2:
        b1 = clean[0:2]
        b2 = f"{random.randint(0, 255):02X}"
        b3 = f"{random.randint(0, 255):02X}"
    else:
        return generate_random_mac()
        
    return f"9C:00:D3:{b1}:{b2}:{b3}"


def get_sequential_mac(base_input: str = None, offset: int = 0, default_prefix_octets: tuple = None) -> str:
    """
    Gera o MAC sequencial de 6 octetos (9C:00:D3:XX:YY:ZZ) incrementando o último octeto ZZ no loop.
    - Se o usuário forneceu 2 octetos (ex: 'F2:72'), fixa XX=F2, YY=72 e varia ZZ de (0 + offset) % 256.
    - Se forneceu 3 octetos (ex: 'F2:72:AA'), fixa XX=F2, YY=72 e varia ZZ de (0xAA + offset) % 256.
    - Se vazio, usa default_prefix_octets (XX, YY) e varia ZZ de (0 + offset) % 256.
    Sempre formata ZZ com {:02X} garantindo 17 caracteres e 6 partes.
    """
    clean = re.sub(r'[^0-9A-Fa-f]', '', base_input or "").upper()
    if clean.startswith("9C00D3"):
        clean = clean[6:]
        
    if len(clean) >= 6:
        b1 = clean[0:2]
        b2 = clean[2:4]
        try:
            start_b3 = int(clean[4:6], 16)
        except ValueError:
            start_b3 = 0
    elif len(clean) >= 4:
        b1 = clean[0:2]
        b2 = clean[2:4]
        start_b3 = 0
    elif len(clean) >= 2:
        b1 = clean[0:2]
        b2 = default_prefix_octets[1] if default_prefix_octets else f"{random.randint(0, 255):02X}"
        start_b3 = 0
    else:
        if default_prefix_octets:
            b1, b2 = default_prefix_octets[0], default_prefix_octets[1]
        else:
            b1 = f"{random.randint(0, 255):02X}"
            b2 = f"{random.randint(0, 255):02X}"
        start_b3 = 0
        
    b3 = (start_b3 + offset) % 256
    return f"9C:00:D3:{b1}:{b2}:{b3:02X}"


def generate_xml_content(mac: str = None) -> str:
    """
    Gera o conteúdo estrito do arquivo cache.config.xml com base no template minimalista.
    Substitui exclusivamente a variável do MAC gerado no loop.
    """
    if not mac or len(mac) != 17 or mac.count(':') != 5:
        mac = normalize_or_generate_mac(mac)
    clean_mac = mac.strip().upper()
    
    return f"""<?xml version='1.0' encoding='utf-8' standalone='yes' ?>
<map>
    <string name="KEY_SP_SN"></string>
    <string name="_free"></string>
    <string name="_special"></string>
    <string name="Special_root"></string>
    <long name="dcs_realtime" value="5432344" />
    <string name="_live"></string>
    <string name="cache_key_recommend"></string>
    <string name="_search"></string>
    <string name="SP_SN_BACKUP">{clean_mac},1</string>
</map>"""


def generate_single_config(
    mac: str = None,
    folder_name: str = "CONFIG_1",
    **kwargs
) -> dict:
    """
    Gera a configuração contendo ESTRITAMENTE apenas o arquivo cache.config.xml.
    """
    if not mac or len(mac) != 17 or mac.count(':') != 5:
        mac = normalize_or_generate_mac(mac)
    else:
        mac = mac.strip().upper()
        
    xml_str = generate_xml_content(mac=mac)
    
    return {
        "folder_name": folder_name,
        "mac": mac,
        "backup_sn": f"{mac},1",
        "files": {
            "cache.config.xml": xml_str
        }
    }


def generate_bulk_configs(
    count: int = 10,
    start_index: int = 1,
    folder_prefix: str = "CONFIG_",
    base_mac: str = None,
    sequential: bool = True,
    **kwargs
) -> list:
    """
    Gera lote de configurações contendo ESTRITAMENTE apenas o arquivo cache.config.xml.
    - MAC de 6 partes e 17 caracteres (9C:00:D3:XX:YY:ZZ).
    - Loop sequencial de 00 a FF com {:02X}.
    """
    results = []
    count = max(1, min(count, 256))
    
    # Sorteia prefixo fixo caso o usuário não tenha passado os 2 octetos
    rand_b1 = f"{random.randint(0, 255):02X}"
    rand_b2 = f"{random.randint(0, 255):02X}"
    default_octets = (rand_b1, rand_b2)
    
    for i in range(count):
        idx = start_index + i
        if sequential:
            mac = get_sequential_mac(base_mac, offset=i, default_prefix_octets=default_octets)
        else:
            mac = normalize_or_generate_mac(base_mac) if base_mac else generate_random_mac()
            
        folder_name = f"{folder_prefix}{idx}"
        cfg = generate_single_config(mac=mac, folder_name=folder_name)
        results.append(cfg)
        
    return results


def create_zip_archive(configs_list: list) -> bytes:
    """Cria um arquivo ZIP em memória contendo as pastas do lote e APENAS o arquivo cache.config.xml"""
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
    """Salva fisicamente as configurações no disco contendo ESTRITAMENTE apenas cache.config.xml"""
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


def parse_and_validate_xml_account(xml_content: str, min_user_id: int = 567000000) -> dict:
    """
    Extrai dados do cache.config.xml gerado no shared_prefs do aplicativo e aplica a regra de validação:
    - Converte key_user_id para Integer.
    - Se key_user_id >= 567000000 -> Conta Nova 0 Dias (Válida / Aprovada)
    - Se key_user_id < 567000000 -> Conta Antiga / Reciclada (Descartada)
    """
    return f"9C:00:D3:{b1:02X}:{b2:02X}:{b3:02X}"


def generate_smart_random_mac() -> str:
    """Gera um MAC no padrão 9C:00:D3:XX:YY:ZZ (prefixo 9C:00:D3: fixo)"""
    return generate_random_mac()


def normalize_or_generate_mac(user_input: str = None) -> str:
    """
    Normaliza a entrada do usuário para garantir um MAC de 6 partes e 17 caracteres (9C:00:D3:XX:YY:ZZ).
    Se incompleto (ex: F2:72), completa os octetos que faltarem.
    """
    if not user_input:
        return generate_random_mac()
        
    clean = re.sub(r'[^0-9A-Fa-f]', '', str(user_input)).upper()
    if clean.startswith("9C00D3"):
        clean = clean[6:]
        
    if len(clean) >= 6:
        b1 = clean[0:2]
        b2 = clean[2:4]
        b3 = clean[4:6]
    elif len(clean) >= 4:
        b1 = clean[0:2]
        b2 = clean[2:4]
        b3 = f"{random.randint(0, 255):02X}"
    elif len(clean) >= 2:
        b1 = clean[0:2]
        b2 = f"{random.randint(0, 255):02X}"
        b3 = f"{random.randint(0, 255):02X}"
    else:
        return generate_random_mac()
        
    return f"9C:00:D3:{b1}:{b2}:{b3}"


def get_sequential_mac(base_input: str = None, offset: int = 0, default_prefix_octets: tuple = None) -> str:
    """
    Gera o MAC sequencial de 6 octetos (9C:00:D3:XX:YY:ZZ) incrementando o último octeto ZZ no loop.
    - Se o usuário forneceu 2 octetos (ex: 'F2:72'), fixa XX=F2, YY=72 e varia ZZ de (0 + offset) % 256.
    - Se forneceu 3 octetos (ex: 'F2:72:AA'), fixa XX=F2, YY=72 e varia ZZ de (0xAA + offset) % 256.
    - Se vazio, usa default_prefix_octets (XX, YY) e varia ZZ de (0 + offset) % 256.
    Sempre formata ZZ com {:02X} garantindo 17 caracteres e 6 partes.
    """
    clean = re.sub(r'[^0-9A-Fa-f]', '', base_input or "").upper()
    if clean.startswith("9C00D3"):
        clean = clean[6:]
        
    if len(clean) >= 6:
        b1 = clean[0:2]
        b2 = clean[2:4]
        try:
            start_b3 = int(clean[4:6], 16)
        except ValueError:
            start_b3 = 0
    elif len(clean) >= 4:
        b1 = clean[0:2]
        b2 = clean[2:4]
        start_b3 = 0
    elif len(clean) >= 2:
        b1 = clean[0:2]
        b2 = default_prefix_octets[1] if default_prefix_octets else f"{random.randint(0, 255):02X}"
        start_b3 = 0
    else:
        if default_prefix_octets:
            b1, b2 = default_prefix_octets[0], default_prefix_octets[1]
        else:
            b1 = f"{random.randint(0, 255):02X}"
            b2 = f"{random.randint(0, 255):02X}"
        start_b3 = 0
        
    b3 = (start_b3 + offset) % 256
    return f"9C:00:D3:{b1}:{b2}:{b3:02X}"


def generate_xml_content(mac: str = None) -> str:
    """
    Gera o conteúdo estrito do arquivo cache.config.xml com base no template minimalista.
    Substitui exclusivamente a variável do MAC gerado no loop.
    """
    if not mac or len(mac) != 17 or mac.count(':') != 5:
        mac = normalize_or_generate_mac(mac)
    clean_mac = mac.strip().upper()
    
    return f"""<?xml version='1.0' encoding='utf-8' standalone='yes' ?>
<map>
    <string name="KEY_SP_SN"></string>
    <string name="_free"></string>
    <string name="_special"></string>
    <string name="Special_root"></string>
    <long name="dcs_realtime" value="5432344" />
    <string name="_live"></string>
    <string name="cache_key_recommend"></string>
    <string name="_search"></string>
    <string name="SP_SN_BACKUP">{clean_mac},1</string>
</map>"""


def generate_single_config(
    mac: str = None,
    folder_name: str = "CONFIG_1",
    **kwargs
) -> dict:
    """
    Gera a configuração contendo ESTRITAMENTE apenas o arquivo cache.config.xml.
    """
    if not mac or len(mac) != 17 or mac.count(':') != 5:
        mac = normalize_or_generate_mac(mac)
    else:
        mac = mac.strip().upper()
        
    xml_str = generate_xml_content(mac=mac)
    
    return {
        "folder_name": folder_name,
        "mac": mac,
        "backup_sn": f"{mac},1",
        "files": {
            "cache.config.xml": xml_str
        }
    }


def generate_bulk_configs(
    count: int = 10,
    start_index: int = 1,
    folder_prefix: str = "CONFIG_",
    base_mac: str = None,
    sequential: bool = True,
    **kwargs
) -> list:
    """
    Gera lote de configurações contendo ESTRITAMENTE apenas o arquivo cache.config.xml.
    - MAC de 6 partes e 17 caracteres (9C:00:D3:XX:YY:ZZ).
    - Loop sequencial de 00 a FF com {:02X}.
    """
    results = []
    count = max(1, min(count, 256))
    
    # Sorteia prefixo fixo caso o usuário não tenha passado os 2 octetos
    rand_b1 = f"{random.randint(0, 255):02X}"
    rand_b2 = f"{random.randint(0, 255):02X}"
    default_octets = (rand_b1, rand_b2)
    
    for i in range(count):
        idx = start_index + i
        if sequential:
            mac = get_sequential_mac(base_mac, offset=i, default_prefix_octets=default_octets)
        else:
            mac = normalize_or_generate_mac(base_mac) if base_mac else generate_random_mac()
            
        folder_name = f"{folder_prefix}{idx}"
        cfg = generate_single_config(mac=mac, folder_name=folder_name)
        results.append(cfg)
        
    return results


def create_zip_archive(configs_list: list) -> bytes:
    """Cria um arquivo ZIP em memória contendo as pastas do lote e APENAS o arquivo cache.config.xml"""
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
    """Salva fisicamente as configurações no disco contendo ESTRITAMENTE apenas cache.config.xml"""
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


def parse_and_validate_xml_account(xml_content: str, min_user_id: int = 567000000) -> dict:
    """
    Extrai dados do cache.config.xml gerado no shared_prefs do aplicativo e aplica a regra de validação:
    - Converte key_user_id para Integer.
    - Se key_user_id >= 567000000 -> Conta Nova 0 Dias (Válida / Aprovada)
    - Se key_user_id < 567000000 -> Conta Antiga / Reciclada (Descartada)
    """
    mac_m = (re.search(r'name="KEY_SP_SN"[^>]*>([^<]+)<', xml_content) or 
             re.search(r'name="SP_SN_BACKUP"[^>]*>([0-9A-Fa-f:]{17})', xml_content) or
             re.search(r'([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})', xml_content))
    mac = mac_m.group(1).upper() if mac_m else ""
    
    uid_m = re.search(r'name="key_user_id"[^>]*>([0-9]+)<', xml_content)
    user_id_str = uid_m.group(1) if uid_m else ""
    user_id_int = 0
    if user_id_str.isdigit():
        try:
            user_id_int = int(user_id_str)
        except (ValueError, TypeError):
            user_id_int = 0
            
    n_bt_m = re.search(r'name="key_n_bt"[^>]*>([^<]+)<', xml_content)
    key_n_bt = n_bt_m.group(1) if n_bt_m else ""
    
    dev_m = re.search(r'name="key_device_id_unitvfree"[^>]*>([^<]+)<', xml_content)
    device_id = dev_m.group(1) if dev_m else ""
    
    # Regra de Validação
    if user_id_int >= min_user_id:
        is_valid = True
        is_virgin = True
        days_active = 0
        folder_name = f"CONFIG_{user_id_int}_0DIAS"
        status = "✨ 0 DIAS (VIRGEM)"
    else:
        is_valid = False
        is_virgin = False
        days_active = None
        folder_name = f"CONFIG_{user_id_int}_{days_active or 0}DIAS" if user_id_int > 0 else "CONFIG_ERRO_EF9"
        status = f"❌ Reciclada/Antiga (< {min_user_id})"
        
    return {
        "user_id": user_id_str,
        "user_id_int": user_id_int,
        "mac": mac,
        "key_n_bt": key_n_bt,
        "device_id": device_id,
        "is_valid": is_valid,
        "is_virgin": is_virgin,
        "days_active": days_active,
        "folder_name": folder_name,
        "status": status
    }


def load_all_existing_configs(base_dir: str = ".") -> list:
    """Carrega e cataloga todas as configurações existentes no diretório local a partir do cache.config.xml"""
    xml_paths = glob.glob(os.path.join(base_dir, '**/cache.config.xml'), recursive=True)
    catalog = []
    
    for path in sorted(xml_paths):
        dirpath = os.path.dirname(path)
        rel = os.path.relpath(dirpath, base_dir).replace('\\', '/')
        if rel == '.' or 'node_modules' in rel or '.git' in rel or '__pycache__' in rel or 'temp' in rel:
            continue
            
        mac = ""
        user_id = ""
        try:
            tree = ET.parse(path)
            for elem in tree.getroot():
                name = elem.get('name')
                val = elem.get('value') if 'value' in elem.attrib else (elem.text or '')
                if name == 'KEY_SP_SN' and val:
                    mac = val
                elif name == 'SP_SN_BACKUP' and val and not mac:
                    mac = val.split(',')[0]
                elif name == 'key_user_id':
                    user_id = val
        except Exception:
            pass
            
        catalog.append({
            "folder": rel,
            "mac": mac,
            "user_id": user_id,
            "path": dirpath
        })
        
    return catalog
