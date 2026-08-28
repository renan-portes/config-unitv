"""
Servidor Web e API REST para o Gerador de Configurações IPTV
Suporta geração local de novas contas, injeção ADB no emulador e integração com o Pool da Nuvem (10.231 configs)
"""

import os
import io
import re
import time
import json
import html
import base64
import random
import subprocess
import requests
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Response, Request, Depends, status
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uvicorn
import jwt
import bcrypt
from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, joinedload

import generator_engine as engine

app = FastAPI(
    title="Gerador de .config IPTV (Local, Nuvem & ADB)",
    description="API e Painel Web para geração de .config, .properties e cache.config.xml com suporte a injeção ADB no emulador e pool da nuvem",
    version="1.5.0"
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

apps_dir = os.path.join(BASE_DIR, "apps")
if os.path.exists(apps_dir):
    app.mount("/apps", StaticFiles(directory=apps_dir), name="apps")


# --- CONFIGURAÇÃO DE BANCO DE DADOS (ORM / AGNOSTIC DATABASE) ---
# A URL de conexão está isolada para fácil migração futura para PostgreSQL (Docker/Portainer/Proxmox)
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'mining_history.db')}")

# Configuração agnóstica para SQLite e PostgreSQL
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
db_engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user", nullable=False) # 'user' ou 'admin'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    history = relationship("AccountHistory", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class AccountHistory(Base):
    __tablename__ = "account_history"

    mac = Column(String(50), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    account_id = Column(String(50), nullable=True)
    days_active = Column(Integer, nullable=True)
    status_message = Column(String(255), nullable=True)
    is_valid = Column(Boolean, default=False, nullable=False)
    tested_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="history")

    def to_dict(self):
        uname = None
        if self.user:
            uname = self.user.username
        elif self.user_id is None:
            uname = "Admin / Sistema"
        else:
            uname = f"User #{self.user_id}"

        return {
            "mac": self.mac,
            "user_id": self.user_id,
            "username": uname,
            "account_id": self.account_id,
            "days_active": self.days_active,
            "status_message": self.status_message,
            "is_valid": self.is_valid,
            "tested_at": self.tested_at.isoformat() if self.tested_at else None
        }


# Inicializa as tabelas no banco de dados e garante migrações de schema
Base.metadata.create_all(bind=db_engine)


def ensure_schema_migrations():
    """Garante que colunas novas como user_id existam em bancos de dados já existentes"""
    try:
        with db_engine.connect() as conn:
            if DATABASE_URL.startswith("sqlite"):
                cursor = conn.exec_driver_sql("PRAGMA table_info(account_history)")
                columns = [row[1] for row in cursor.fetchall()]
                if columns and "user_id" not in columns:
                    conn.exec_driver_sql("ALTER TABLE account_history ADD COLUMN user_id INTEGER REFERENCES users(id)")
                    conn.commit()
    except Exception as e:
        print(f"[DB Migration Note] {e}")


ensure_schema_migrations()


# --- CONFIGURAÇÃO DE SEGURANÇA E JWT ---
JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-mining-key-saas-unitv-2026-auth-token-key-32b")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.environ.get("JWT_EXPIRATION_HOURS", "24"))

security_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Gera hash seguro bcrypt da senha"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verifica se a senha em texto puro corresponde ao hash bcrypt"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user: User, expires_delta: Optional[timedelta] = None) -> str:
    """Gera um token JWT assinado com dados do usuário e data de expiração"""
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=JWT_EXPIRATION_HOURS))
    payload = {
        "sub": user.username,
        "user_id": user.id,
        "role": user.role,
        "exp": expire
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decodifica e valida o token JWT"""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado. Por favor, faça login novamente.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticação inválido.",
            headers={"WWW-Authenticate": "Bearer"}
        )


def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)) -> User:
    """
    Dependência FastAPI para validar o token JWT e retornar o usuário autenticado.
    Suporta header Authorization: Bearer <token>.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticação não fornecido.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("user_id")
    username = payload.get("sub")

    if not user_id and not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais do token inválidas.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    session = SessionLocal()
    try:
        user = None
        if user_id:
            user = session.query(User).filter(User.id == user_id).first()
        elif username:
            user = session.query(User).filter(User.username == username).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuário não encontrado.",
                headers={"WWW-Authenticate": "Bearer"}
            )
        return user
    finally:
        session.close()


def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)) -> Optional[User]:
    """Dependência opcional para rotas que podem ser anônimas ou autenticadas"""
    if not credentials or not credentials.credentials:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("user_id")
        username = payload.get("sub")
        if not user_id and not username:
            return None
        session = SessionLocal()
        try:
            if user_id:
                return session.query(User).filter(User.id == user_id).first()
            return session.query(User).filter(User.username == username).first()
        finally:
            session.close()
    except Exception:
        return None


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependência para proteção de rotas exclusivas para administradores"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito para administradores."
        )
    return current_user


def save_account_history(
    mac: str,
    user_id: Optional[int] = None,
    account_id: Optional[str] = None,
    days_active: Optional[int] = None,
    status_message: Optional[str] = None,
    is_valid: bool = False
) -> Optional[AccountHistory]:
    """
    Persiste ou atualiza atomicamente o histórico de teste de um MAC usando session.merge().
    Relaciona o registro ao user_id do cliente autenticado (Multi-tenant).
    MACs rejeitados (EF9, Falha no acesso, Bloqueio, etc.) são gravados com is_valid=False.
    """
    if not mac or mac == "-" or not isinstance(mac, str):
        return None

    mac_clean = mac.strip().upper()
    if len(mac_clean) < 12:
        return None

    session = SessionLocal()
    try:
        existing = session.query(AccountHistory).filter(AccountHistory.mac == mac_clean).first()
        final_user_id = user_id if user_id is not None else (existing.user_id if existing else None)

        record = AccountHistory(
            mac=mac_clean,
            user_id=final_user_id,
            account_id=str(account_id) if (account_id and str(account_id) != "-") else None,
            days_active=days_active if isinstance(days_active, int) else None,
            status_message=status_message or "Desconhecido",
            is_valid=bool(is_valid),
            tested_at=datetime.utcnow()
        )
        merged = session.merge(record)
        session.commit()
        session.refresh(merged)
        return merged
    except Exception as e:
        session.rollback()
        print(f"[DB History Error] Falha ao persistir histórico para o MAC {mac_clean}: {e}")
        return None
    finally:
        session.close()


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


class LoginRequest(BaseModel):
    username: str
    password: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: Optional[str] = "user"


# --- ROTAS DE AUTENTICAÇÃO & ADMINISTRAÇÃO (SaaS / JWT) ---

@app.post("/api/auth/login")
def login(req: LoginRequest):
    """
    Valida as credenciais do usuário e retorna o token de acesso JWT.
    """
    if not req.username or not req.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário e senha são obrigatórios."
        )

    session = SessionLocal()
    try:
        user = session.query(User).filter(User.username == req.username.strip()).first()
        if not user or not verify_password(req.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuário ou senha incorretos.",
                headers={"WWW-Authenticate": "Bearer"}
            )

        token = create_access_token(user)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": user.to_dict()
        }
    finally:
        session.close()


@app.get("/api/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Retorna os dados do usuário autenticado atual"""
    return {
        "user": current_user.to_dict()
    }


@app.get("/api/admin/users")
def list_admin_users(current_admin: User = Depends(get_current_admin)):
    """
    Retorna a lista de todos os usuários cadastrados no sistema (Apenas Administradores).
    """
    session = SessionLocal()
    try:
        users = session.query(User).order_by(User.id.asc()).all()
        return {
            "total": len(users),
            "users": [u.to_dict() for u in users]
        }
    finally:
        session.close()


@app.post("/api/admin/users")
def create_admin_user(
    req: CreateUserRequest,
    current_admin: User = Depends(get_current_admin)
):
    """
    Cria um novo usuário ou administrador no sistema (Apenas Administradores).
    """
    username_clean = req.username.strip()
    if not username_clean:
        raise HTTPException(status_code=400, detail="Nome de usuário não pode ser vazio.")
    if not req.password:
        raise HTTPException(status_code=400, detail="A senha não pode ser vazia.")

    role_clean = (req.role or "user").strip().lower()
    if role_clean not in ("user", "admin"):
        role_clean = "user"

    session = SessionLocal()
    try:
        existing = session.query(User).filter(User.username == username_clean).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"O usuário '{username_clean}' já existe.")

        new_user = User(
            username=username_clean,
            password_hash=hash_password(req.password),
            role=role_clean
        )
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        return {
            "success": True,
            "message": f"Usuário '{username_clean}' criado com sucesso!",
            "user": new_user.to_dict()
        }
    finally:
        session.close()


@app.get("/api/vault/export-virgins")
def export_virgins(current_user: User = Depends(get_current_user)):
    """
    Retorna apenas os registros onde is_valid == True e days_active == 0 (Contas Virgens).
    Multi-tenant: Usuários comuns recebem apenas suas contas virgens.
    Administradores recebem todas as contas virgens do sistema.
    """
    session = SessionLocal()
    try:
        query = session.query(AccountHistory).options(joinedload(AccountHistory.user)).filter(
            AccountHistory.is_valid == True,
            AccountHistory.days_active == 0
        )

        if current_user.role != "admin":
            query = query.filter(AccountHistory.user_id == current_user.id)

        records = query.order_by(AccountHistory.tested_at.desc()).all()
        return {
            "total": len(records),
            "user_role": current_user.role,
            "virgins": [r.to_dict() for r in records]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao exportar contas virgens: {str(e)}")
    finally:
        session.close()


# --- ROTAS DA API ---

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "config-generator", "version": "1.5.0", "mode": "saas-multi-tenant"}


@app.get("/api/history")
def get_mining_history(
    limit: int = 1000,
    current_user: User = Depends(get_current_user)
):
    """
    Retorna o histórico de MACs testados ordenados por tested_at decrescente (padrão: últimos 1000).
    Multi-tenant: Usuários comuns visualizam apenas seus próprios registros.
    Administradores (role='admin') visualizam todo o histórico do sistema.
    """
    session = SessionLocal()
    try:
        limit_val = min(max(1, limit), 5000)
        query = session.query(AccountHistory).options(joinedload(AccountHistory.user))

        # Isolamento Multi-tenant
        if current_user.role != "admin":
            query = query.filter(AccountHistory.user_id == current_user.id)

        records = query.order_by(AccountHistory.tested_at.desc()).limit(limit_val).all()
        return {
            "total": len(records),
            "user_role": current_user.role,
            "history": [r.to_dict() for r in records]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar histórico: {str(e)}")
    finally:
        session.close()


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


UNITV_PACKAGES = ["com.integration.unitvsiptv", "com.unitv.freetv"]


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
            "READ_MEDIA_AUDIO",
            "READ_MEDIA_IMAGES",
            "READ_MEDIA_VIDEO",
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
    """
    Executa o Smart Wipe (Limpeza Inteligente) sem 'pm clear' (OTIMIZAÇÃO 1):
    1. adb shell am force-stop (força a parada obrigatória do app).
    2. Deleta backups ocultos em storage e sdcard para evitar MACs fantasmas.
    3. Preserva as flags de interface em shared_prefs (impedindo o reaparecimento de tutoriais).
    4. Concede permissões necessárias.
    """
    adb_bin = get_adb_cmd()
    
    # 1. Força a parada do aplicativo
    for pkg in UNITV_PACKAGES:
        subprocess.run([adb_bin, "-s", device, "shell", f"am force-stop {pkg}"], capture_output=True, timeout=5)
        
    # 2. Deleta backups ocultos em storage e sdcard (evita MACs fantasmas)
    subprocess.run([adb_bin, "-s", device, "shell", "rm -rf /storage/emulated/0/Android/.config /sdcard/Android/.config /storage/emulated/0/.config /sdcard/.config /sdcard/.properties /storage/emulated/0/.properties /sdcard/Alarms/system_uf /sdcard/cache.config.xml /storage/emulated/0/cache.config.xml /sdcard/window_dump.xml"], capture_output=True, timeout=5)
    
    # 3. Reconcede permissões completas
    grant_all_app_permissions(device)


def smart_wipe_emulator(device: str):
    """Alias para Smart Wipe"""
    return deep_wipe_emulator(device)


@app.post("/api/adb/clear-app")
def clear_app_data(req: Optional[dict] = None):
    """Limpa dados do aplicativo e configs antigas no emulador e reconcede permissões"""
    global current_active_adb_device
    device = (req or {}).get("device_addr") or current_active_adb_device or "127.0.0.1:21503"
    try:
        ensure_adb_connected(device)
        deep_wipe_emulator(device)
        return {"success": True, "message": "Deep Wipe realizado com sucesso no emulador!"}
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
        for pkg in UNITV_PACKAGES:
            subprocess.run([adb_bin, "-s", device, "shell", f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1"], capture_output=True, text=True, timeout=5)
        return {"success": True, "message": "UniTV Free iniciado no emulador!"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_app_lifecycle_and_guide(device: str, max_wait_sec: int = 15) -> bool:
    """
    Aguarda o ciclo de inicialização do app com detecção precoce de erro EF9:
    - WelcomeActivity -> aguarda carregar com segurança.
    - GuidePageActivity -> avança os slides com DPAD_CENTER / ENTER.
    - HomeActivity -> sincroniza com o servidor.
    - EF9 / Falha de Login -> interrompe precocemente.
    """
    adb_bin = get_adb_cmd()
    home_reached = False
    
    for sec in range(max_wait_sec):
        res = subprocess.run([adb_bin, "-s", device, "shell", "dumpsys window | grep -E mCurrentFocus"], capture_output=True, text=True, errors='ignore', timeout=3)
        focus = res.stdout or ""
        
        # 1. Checa se o cache.config.xml já foi autenticado pelo servidor
        for pkg in UNITV_PACKAGES:
            r_xml = subprocess.run([adb_bin, "-s", device, "shell", f"su -c 'cat /data/data/{pkg}/shared_prefs/cache.config.xml'"], capture_output=True, text=True, errors='ignore', timeout=2)
            xml_text = r_xml.stdout or ""
            if 'name="key_user_id"' in xml_text and '<string name="key_user_id"></string>' not in xml_text:
                m_uid = re.search(r'name="key_user_id"[^>]*>([0-9]+)<', xml_text)
                if m_uid and m_uid.group(1).strip():
                    home_reached = True
                    break
        if home_reached:
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
    """Função de compatibilidade que aciona o manipulador de ciclo de vida"""
    return handle_app_lifecycle_and_guide(device, max_wait_sec=8)


def parse_profile_dump(dump_xml_str: str) -> tuple[Optional[str], Optional[int], Optional[str], bool]:
    """
    Analisa o dump XML do uiautomator com suporte a quebras de linha (\\n, &#10;),
    espaços múltiplos e nós separados.
    Retorna: (activation_date, days_active, status_msg, has_access_error)
    """
    if not dump_xml_str:
        return None, None, None, False
        
    decoded_xml = html.unescape(dump_xml_str)
    raw_texts = re.findall(r'(?:text|content-desc)="([^"]*)"', decoded_xml)
    
    activation_date = None
    days_active = None
    status_msg = None
    has_access_error = False
    
    normalized_texts = []
    for t in raw_texts:
        norm = " ".join(t.replace("\r", " ").replace("\n", " ").split()).strip()
        if norm:
            normalized_texts.append(norm)
            
    all_text_combined = " ".join(normalized_texts)
    lower_combined = all_text_combined.lower()
    
    if any(k in lower_combined for k in ["falha no acesso", "tente novamente", "rejeitada", "ef9", "a conta foi bloqueada", "bloqueada", "device limit", "limite de dispositivo"]):
        has_access_error = True
        if "bloqueada" in lower_combined:
            status_msg = "❌ A conta foi bloqueada"
        elif "device limit" in lower_combined or "limite" in lower_combined:
            status_msg = "❌ Device limit excedido"
        elif "ef9" in lower_combined or "falha ao fazer login" in lower_combined:
            status_msg = "❌ EF9: Falha ao fazer login"
        else:
            status_msg = "❌ Falha no Acesso / Rejeitada"
        
    # 1. Busca data de ativação (logo após 'ativada em')
    m_date = re.search(r'ativada\s+em\s*[:\s]*([0-9]{2}[\-\/][0-9]{2}[\-\/][0-9]{4})', all_text_combined, re.IGNORECASE)
    if m_date:
        activation_date = m_date.group(1).replace('/', '-')
    else:
        m_date_any = re.search(r'([0-9]{2}[\-\/][0-9]{2}[\-\/][0-9]{4})', all_text_combined)
        if m_date_any:
            activation_date = m_date_any.group(1).replace('/', '-')
            
    # 2. Busca quantidade de dias ativos (logo após 'ativa por' ou antes de 'dias')
    m_days_ativa_por = re.search(r'ativa\s+por\s*([0-9]+)', all_text_combined, re.IGNORECASE)
    if m_days_ativa_por:
        days_active = int(m_days_ativa_por.group(1))
    else:
        m_days_dias = re.search(r'([0-9]+)\s*dias', all_text_combined, re.IGNORECASE)
        if m_days_dias:
            days_active = int(m_days_dias.group(1))
            
    return activation_date, days_active, status_msg, has_access_error


def clean_xml_output(raw_output: str) -> str:
    """Remove cabeçalhos de console antes da tag raiz do XML do uiautomator dump"""
    if not raw_output:
        return ""
    if "<?xml" in raw_output:
        return raw_output[raw_output.find("<?xml"):]
    elif "<hierarchy" in raw_output:
        return raw_output[raw_output.find("<hierarchy"):]
    return raw_output


def parse_bounds(bounds_str: str) -> Optional[tuple[int, int]]:
    """Calcula o ponto central (x, y) a partir de bounds='[x1,y1][x2,y2]'"""
    if not bounds_str:
        return None
    m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
    if m:
        x1, y1, x2, y2 = map(int, m.groups())
        return ((x1 + x2) // 2, (y1 + y2) // 2)
    return None


def get_device_screen_resolution(device: str) -> tuple[int, int]:
    """Captura a resolução real da tela do dispositivo via adb shell wm size (ex: 1600x900)"""
    try:
        adb_bin = get_adb_cmd()
        res = subprocess.run([adb_bin, "-s", device, "shell", "wm size"], capture_output=True, text=True, errors='ignore', timeout=3)
        out = res.stdout or ""
        m = re.findall(r'(?:Physical size|Override size):\s*(\d+)x(\d+)', out)
        if m:
            w, h = map(int, m[-1])
            return w, h
    except Exception:
        pass
    return 1600, 900


def is_unitv_in_foreground(device: str) -> bool:
    """Verifica se uma janela do UniTV está em primeiro plano"""
    adb_bin = get_adb_cmd()
    r = subprocess.run([adb_bin, "-s", device, "shell", "dumpsys window | grep -E mCurrentFocus"], capture_output=True, text=True, errors='ignore', timeout=3)
    focus = r.stdout or ""
    return any(pkg in focus for pkg in UNITV_PACKAGES)


def ensure_unitv_foreground(device: str):
    """Garante que o aplicativo UniTV está em primeiro plano"""
    adb_bin = get_adb_cmd()
    if not is_unitv_in_foreground(device):
        for pkg in UNITV_PACKAGES:
            subprocess.run([adb_bin, "-s", device, "shell", f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1"], capture_output=True, text=True, timeout=5)
        time.sleep(2.0)


def get_emulator_ui_dump(device: str) -> str:
    """Captura e limpa o dump XML do uiautomator no emulador"""
    adb_bin = get_adb_cmd()
    try:
        subprocess.run([adb_bin, "-s", device, "shell", "rm -f /sdcard/window_dump.xml"], capture_output=True, timeout=2)
        subprocess.run([adb_bin, "-s", device, "shell", "uiautomator dump --compressed /sdcard/window_dump.xml || uiautomator dump /sdcard/window_dump.xml"], capture_output=True, text=True, errors='ignore', timeout=6)
        r_cat = subprocess.run([adb_bin, "-s", device, "shell", "cat /sdcard/window_dump.xml"], capture_output=True, text=True, errors='ignore', timeout=3)
        return clean_xml_output(r_cat.stdout or "")
    except Exception:
        return ""


def check_screen_error(dump_xml_str: str) -> Optional[str]:
    """
    Analisa o XML do uiautomator na tela inicial para identificar erros de bloqueio,
    limite de dispositivos ou falhas de autenticação precoces.
    """
    if not dump_xml_str:
        return None
    decoded_xml = html.unescape(dump_xml_str)
    raw_texts = re.findall(r'(?:text|content-desc)="([^"]*)"', decoded_xml)
    combined = " ".join(raw_texts).lower()
    
    if "a conta foi bloqueada" in combined or "conta bloqueada" in combined or "bloqueada" in combined:
        return "❌ A conta foi bloqueada"
    if "device limit" in combined or "limite de dispositivo" in combined or "dispositivo não autorizado" in combined or "excedeu o limite" in combined:
        return "❌ Device limit excedido"
    if "ef9" in combined or "falha ao fazer login" in combined or "falha de login" in combined:
        return "❌ EF9: Falha ao fazer login"
    if "falha no acesso" in combined or "rejeitada" in combined or "tente novamente" in combined or "conta inválida" in combined:
        return "❌ Falha no Acesso / Rejeitada"
    return None


def is_profile_screen_open(xml_text: str) -> bool:
    """Verifica se o fragmento/diálogo de perfil já está carregado e visível na tela"""
    if not xml_text:
        return False
    return any(k in xml_text for k in ["personalFragment", "PersonalFragment", "tvUserName", "tvExpiredTime", "Sua conta foi ativada em", "Meus Favoritos", "Minha Lista", "mTvUserTitle"])


def find_guide_button_in_xml(xml_text: str) -> Optional[tuple[tuple[int, int], str]]:
    """
    Localiza semanticamente o botão 'Próximo', 'OK' ou overlays de tutorial no dump XML.
    Retorna: ((center_x, center_y), descricao)
    """
    if not xml_text:
        return None
    try:
        root = ET.fromstring(xml_text)
        # 1. Procura por textos de botões de avanço e dispensação
        target_texts = ["próximo", "proximo", "ok", "entendi", "pular", "avançar", "começar", "continuar", "next"]
        for elem in root.iter('node'):
            t = (elem.get('text') or '').strip().lower()
            d = (elem.get('content-desc') or '').strip().lower()
            if any(t == target or target in t for target in target_texts) or any(d == target or target in d for target in target_texts):
                b = elem.get('bounds')
                pt = parse_bounds(b)
                if pt:
                    return pt, f"text='{elem.get('text') or elem.get('content-desc')}'"
                    
        # 2. Procura por resource-id de tutorial / viewpager de guia
        for elem in root.iter('node'):
            r_id = (elem.get('resource-id') or '').lower()
            if any(k in r_id for k in ['mivguide', 'mguideviewpager', 'guide', 'tutorial', 'btn_next', 'btn_ok']):
                b = elem.get('bounds')
                pt = parse_bounds(b)
                if pt:
                    return pt, f"res_id='{elem.get('resource-id')}'"
    except Exception:
        pass
    return None


def find_profile_button_in_xml(xml_text: str) -> Optional[tuple[tuple[int, int], str]]:
    """
    Localiza semanticamente o botão de perfil no dump XML.
    Retorna: ((center_x, center_y), descricao)
    """
    if not xml_text:
        return None
    try:
        root = ET.fromstring(xml_text)
        
        # 1. Procura por resource-id de perfil
        for elem in root.iter('node'):
            r_id = (elem.get('resource-id') or '')
            r_id_l = r_id.lower()
            if any(k in r_id_l for k in ['mivpersonal', 'mlayoutpersonal', 'profile', 'personal', 'account', 'user_icon', 'avatar']):
                b = elem.get('bounds')
                pt = parse_bounds(b)
                if pt:
                    return pt, f"res_id='{r_id}'"
                    
        # 2. Procura por content-desc de perfil
        for elem in root.iter('node'):
            d = (elem.get('content-desc') or '').strip().lower()
            if any(k in d for k in ['profile', 'perfil', 'minha conta', 'meu perfil']):
                b = elem.get('bounds')
                pt = parse_bounds(b)
                if pt:
                    return pt, f"content-desc='{elem.get('content-desc')}'"
                    
        # 3. Posição relativa: elemento clicável no header da barra superior direita
        candidates = []
        for elem in root.iter('node'):
            clickable = elem.get('clickable') == 'true'
            bounds = elem.get('bounds')
            if bounds:
                m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                if m:
                    x1, y1, x2, y2 = map(int, m.groups())
                    if clickable and y1 < 180 and x1 >= 1000:
                        cx = (x1 + x2) // 2
                        cy = (y1 + y2) // 2
                        candidates.append(((cx, cy), f"header bounds='{bounds}'"))
        if candidates:
            return candidates[-1][0], candidates[-1][1]
    except Exception:
        pass
    return None


def is_home_screen_rendered(xml_text: str) -> bool:
    """Verifica se a tela principal (Home) do aplicativo UniTV está carregada e visível"""
    if not xml_text:
        return False
    if is_profile_screen_open(xml_text):
        return True
    # Ignora a tela de Splash/Boas-vindas (que contém apenas mTextAppName e mTextVersion)
    if "mTextVersion" in xml_text and "mIvPersonal" not in xml_text and "mGridTab" not in xml_text:
        return False
    if any(k in xml_text for k in ["mLayoutPersonal", "mIvPersonal", "PersonalFragment", "personalFragment"]):
        return True
    if find_profile_button_in_xml(xml_text) is not None:
        return True
    if any(k in xml_text for k in ["mRlTabItem", "mGridTab", "mLvChannelList", "mLayoutChannel", "mLayoutVod"]):
        return True
    return False


def dismiss_tutorials_semantic(device: str, max_attempts: int = 5) -> bool:
    """
    Bypass semântico de tutoriais e overlays via UiAutomator:
    Analisa a árvore XML, localiza botões como 'Próximo', 'OK' ou viewpagers de guia
    e clica no ponto central exato dos bounds.
    """
    adb_bin = get_adb_cmd()
    ensure_unitv_foreground(device)
    
    for attempt in range(max_attempts):
        xml_dump = get_emulator_ui_dump(device)
        if not xml_dump:
            time.sleep(1.0)
            continue
            
        if is_profile_screen_open(xml_dump):
            return True
            
        # Se a Home principal está livre de guias e os botões da barra estão visíveis
        if "mLayoutPersonal" in xml_dump or ("mTextAppName" in xml_dump and "mIvGuide" not in xml_dump and "mGuideViewPager" not in xml_dump):
            return True
            
        guide_match = find_guide_button_in_xml(xml_dump)
        if guide_match:
            (cx, cy), desc = guide_match
            subprocess.run([adb_bin, "-s", device, "shell", f"input tap {cx} {cy}"], timeout=2)
            time.sleep(1.2)
            continue
            
        # Envia toque neutro no centro da tela para fechar pop-ups com dismiss-on-touch-outside
        subprocess.run([adb_bin, "-s", device, "shell", "input tap 800 450"], timeout=2)
        time.sleep(1.0)
        
    return True


def dismiss_tutorials(device: str):
    """Função wrapper de bypass"""
    return dismiss_tutorials_semantic(device)


def dismiss_tutorial_and_overlays(device: str):
    """Alias de compatibilidade"""
    return dismiss_tutorials_semantic(device)


def wait_for_home_or_error(device: str, max_attempts: int = 15, delay_per_attempt: float = 1.5) -> tuple[bool, Optional[str]]:
    """
    Polling dinâmico via uiautomator dump aguardando a renderização da tela principal (Home)
    ou a identificação imediata de erros/bloqueios na tela inicial.
    Retorna: (is_home_ready, error_message)
    """
    adb_bin = get_adb_cmd()
    ensure_unitv_foreground(device)
    
    for attempt in range(1, max_attempts + 1):
        xml_dump = get_emulator_ui_dump(device)
        
        if xml_dump:
            # 1. Verifica erros/bloqueios explícitos na tela inicial
            err = check_screen_error(xml_dump)
            if err:
                return False, err
                
            # 2. Verifica se algum tutorial / diálogo de permissão está bloqueando a tela
            guide_match = find_guide_button_in_xml(xml_dump)
            if guide_match:
                (cx, cy), desc = guide_match
                subprocess.run([adb_bin, "-s", device, "shell", f"input tap {cx} {cy}"], timeout=2)
                time.sleep(1.0)
                continue
                
            # 3. Verifica se a Home já está renderizada ou Perfil já aberto
            if is_home_screen_rendered(xml_dump):
                return True, None

        time.sleep(delay_per_attempt)
        
    return False, "❌ Timeout: Tela inicial não renderizada"


def click_profile_semantic(device: str, max_retries: int = 4) -> bool:
    """
    Localiza e clica no botão de perfil com Retry Loop blindado:
    Se o clique não abrir o perfil (personalFragment), repete o clique dinamicamente até abrir.
    Usa coordenadas responsivas (wm size) no fallback.
    """
    adb_bin = get_adb_cmd()
    ensure_unitv_foreground(device)
    
    for attempt in range(1, max_retries + 1):
        xml_dump = get_emulator_ui_dump(device)
        if is_profile_screen_open(xml_dump):
            return True
            
        profile_match = find_profile_button_in_xml(xml_dump)
        if profile_match:
            (cx, cy), desc = profile_match
            subprocess.run([adb_bin, "-s", device, "shell", f"input tap {cx} {cy}"], timeout=2)
        else:
            # Fallback responsivo baseado na resolução real do dispositivo
            w, h = get_device_screen_resolution(device)
            if w >= h: # Landscape
                fx = int(w * 0.95)
                fy = int(h * 0.08)
            else: # Portrait
                fx = int(w * 0.90)
                fy = int(h * 0.05)
            subprocess.run([adb_bin, "-s", device, "shell", f"input tap {fx} {fy}"], timeout=2)
            
        time.sleep(1.2)
        
        # Verifica se o clique abriu a tela de perfil
        check_dump = get_emulator_ui_dump(device)
        if is_profile_screen_open(check_dump):
            return True
            
    return is_profile_screen_open(get_emulator_ui_dump(device))


def inspect_emulator_account_info(
    device: str = "127.0.0.1:21503",
    expected_config_content: str = None,
    target_mac: Optional[str] = None,
    user_id: Optional[int] = None
) -> dict:
    """
    Lê as informações da conta diretamente da interface do app no emulador
    com Smart Wait orientado a eventos, Retry Loop no clique do perfil,
    detecção precoce de erros, salvamento no padrão CONFIG_{IDCONTA}_{DIAS}DIAS
    e gravação automática no banco de dados ORM (AccountHistory) vinculando ao user_id.
    """
    try:
        if not target_mac and expected_config_content:
            m_mac_exp = re.search(r'SP_SN_BACKUP">([0-9A-Fa-f:]{17})', expected_config_content) or re.search(r'KEY_SP_SN">([0-9A-Fa-f:]{17})', expected_config_content)
            if m_mac_exp:
                target_mac = m_mac_exp.group(1).upper()

        adb_bin = get_adb_cmd()
        grant_all_app_permissions(device)
        
        # 1. Espera Dinâmica da Home (Smart Wait) e Detecção Precoce de Erro
        home_ready, early_error = wait_for_home_or_error(device, max_attempts=15, delay_per_attempt=1.5)
        
        # Leitura do cache.config.xml no shared_prefs
        xml_stdout = ""
        for pkg in UNITV_PACKAGES:
            r_xml = subprocess.run([adb_bin, "-s", device, "shell", f"su -c 'cat /data/data/{pkg}/shared_prefs/cache.config.xml'"], capture_output=True, text=True, errors='ignore', timeout=3)
            if r_xml.stdout and "<map>" in r_xml.stdout:
                xml_stdout = r_xml.stdout
                break
                
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

        final_mac = (app_mac if (app_mac and app_mac != "-") else target_mac) or "-"

        # Se detectou erro explícito na tela inicial durante o Smart Wait
        if early_error:
            subprocess.run([adb_bin, "-s", device, "shell", "input keyevent KEYCODE_BACK"], timeout=2)
            user_id_int = int(account_id) if (account_id and account_id.isdigit()) else 0
            save_account_history(
                mac=final_mac,
                user_id=user_id,
                account_id=str(user_id_int) if user_id_int > 0 else None,
                days_active=None,
                status_message=early_error,
                is_valid=False
            )
            return {
                "found": False,
                "account_id": str(user_id_int) if user_id_int > 0 else "-",
                "user_id_int": user_id_int,
                "activation_date": "-",
                "days_active": None,
                "expiration_date": "-",
                "status_message": early_error,
                "is_valid": False,
                "mac": final_mac or "-",
                "key_n_bt": key_n_bt,
                "folder_name": f"CONFIG_{user_id_int}_ERRO" if user_id_int > 0 else "CONFIG_ERRO_REJEITADA"
            }

        # Se não há key_user_id no XML nem renderizou a Home, a conta foi rejeitada
        if not account_id and not home_ready:
            subprocess.run([adb_bin, "-s", device, "shell", "input keyevent KEYCODE_BACK"], timeout=2)
            err_msg = "❌ EF9: Falha ao fazer login"
            save_account_history(
                mac=final_mac,
                user_id=user_id,
                account_id=None,
                days_active=None,
                status_message=err_msg,
                is_valid=False
            )
            return {
                "found": False,
                "account_id": "-",
                "user_id_int": 0,
                "activation_date": "-",
                "days_active": None,
                "expiration_date": "-",
                "status_message": err_msg,
                "is_valid": False,
                "mac": final_mac or "-",
                "key_n_bt": key_n_bt,
                "folder_name": "CONFIG_ERRO_EF9"
            }

        # 2. Clique de Perfil Blindado (Retry Loop)
        activation_date = None
        days_active = None
        status_msg = None
        has_access_error = False
        
        try:
            click_profile_semantic(device, max_retries=4)
            
            # 3. Loop de Leitura do Diálogo do Perfil
            for attempt in range(12):
                time.sleep(0.8)
                dump_str = get_emulator_ui_dump(device)
                
                # Se a tela de perfil fechou ou não abriu, refaz o clique
                if not is_profile_screen_open(dump_str):
                    if attempt in (2, 5, 8):
                        click_profile_semantic(device, max_retries=2)
                    continue
                    
                parsed_date, parsed_days, parsed_status, parsed_access_error = parse_profile_dump(dump_str)
                if parsed_access_error:
                    has_access_error = True
                    status_msg = parsed_status
                if parsed_date:
                    activation_date = parsed_date
                if parsed_days is not None:
                    days_active = parsed_days
                    
                if (days_active is not None and activation_date) or has_access_error:
                    break
                    
            # Fecha o diálogo de perfil após ler
            subprocess.run([adb_bin, "-s", device, "shell", "input keyevent KEYCODE_BACK"], timeout=2)
        except Exception:
            pass

        # 4. Releitura de confirmação do cache.config.xml
        for pkg in UNITV_PACKAGES:
            r_xml = subprocess.run([adb_bin, "-s", device, "shell", f"su -c 'cat /data/data/{pkg}/shared_prefs/cache.config.xml'"], capture_output=True, text=True, errors='ignore', timeout=3)
            if r_xml.stdout and "<map>" in r_xml.stdout:
                xml_stdout = r_xml.stdout
                break
        if xml_stdout:
            uid_match = re.search(r'name="key_user_id"[^>]*>([0-9]+)<', xml_stdout)
            if uid_match and uid_match.group(1).strip():
                account_id = uid_match.group(1).strip()

        # 5. Validação Estrita do ID e dos Dias Ativos
        user_id_int = int(account_id) if (account_id and account_id.isdigit()) else 0
        
        if not account_id or user_id_int == 0 or has_access_error:
            is_valid = False
            status_msg = status_msg or "❌ Falha no Acesso / Inválida"
            folder_name = f"CONFIG_{user_id_int}_{days_active or 0}DIAS" if user_id_int > 0 else "CONFIG_ERRO_EF9"
            save_account_history(
                mac=final_mac,
                user_id=user_id,
                account_id=str(user_id_int) if user_id_int > 0 else None,
                days_active=days_active,
                status_message=status_msg,
                is_valid=False
            )
            return {
                "found": False,
                "account_id": str(user_id_int) if user_id_int > 0 else "-",
                "user_id_int": user_id_int,
                "activation_date": activation_date or "-",
                "days_active": days_active,
                "expiration_date": "-",
                "status_message": status_msg,
                "is_valid": False,
                "mac": final_mac or "-",
                "key_n_bt": key_n_bt,
                "folder_name": folder_name
            }

        if user_id_int >= 567000000:
            is_valid = True
            if days_active is None:
                days_active = 0
            if days_active == 0:
                status_msg = "✨ 0 DIAS (VIRGEM)"
            else:
                status_msg = f"⭐ {days_active} DIAS"
        else:
            is_valid = False
            if days_active is not None:
                status_msg = f"❌ {days_active}d (< 567M Reciclada)"
            else:
                status_msg = f"❌ Reciclada (ID: {user_id_int} < 567M)"

        if not activation_date:
            activation_date = datetime.now().strftime("%d-%m-%Y")

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

        # 6. Nomenclatura Dinâmica Estrita: CONFIG_{IDCONTA}_{DIAS}DIAS
        days_val = days_active if days_active is not None else 0
        folder_name = f"CONFIG_{user_id_int}_{days_val}DIAS"

        # 7. Salva backup na pasta configs/CONFIG_{ID}_{DIAS}DIAS/ contendo EXCLUSIVAMENTE o cache.config.xml
        save_dir = os.path.join(BASE_DIR, "configs", folder_name)
        os.makedirs(save_dir, exist_ok=True)
        
        dest_xml_file = os.path.join(save_dir, "cache.config.xml")
        
        pulled_content = ""
        for pkg in UNITV_PACKAGES:
            r_pull = subprocess.run([adb_bin, "-s", device, "shell", f"su -c 'cat /data/data/{pkg}/shared_prefs/cache.config.xml'"], capture_output=True, text=True, errors='ignore', timeout=3)
            if r_pull.stdout and "<map>" in r_pull.stdout:
                pulled_content = r_pull.stdout
                break
                
        final_xml_content = pulled_content or xml_stdout or engine.generate_xml_content(mac=app_mac)
        with open(dest_xml_file, "w", encoding="utf-8") as f:
            f.write(final_xml_content)

        save_account_history(
            mac=final_mac,
            user_id=user_id,
            account_id=str(user_id_int),
            days_active=days_active,
            status_message=status_msg,
            is_valid=is_valid
        )

        return {
            "found": True,
            "account_id": str(user_id_int),
            "user_id_int": user_id_int,
            "activation_date": activation_date,
            "days_active": days_active,
            "expiration_date": expiration_date,
            "status_message": status_msg,
            "is_valid": is_valid,
            "mac": final_mac or "-",
            "key_n_bt": key_n_bt,
            "folder_name": folder_name
        }
    except Exception as e:
        err_msg = f"❌ Erro na inspeção: {str(e)}"
        if target_mac and target_mac != "-":
            save_account_history(
                mac=target_mac,
                user_id=user_id,
                account_id=None,
                days_active=None,
                status_message=err_msg,
                is_valid=False
            )
        return {"found": False, "error": str(e)}


@app.post("/api/adb/inject")
def inject_adb(
    req: ADBInjectRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Injeta arquivos de configuração no emulador Android via ADB:
    1. Executa Limpeza Profunda (Deep Wipe) estrita do emulador
    2. Envia exclusivamente o novo cache.config.xml
    3. Abre o app e aciona Smart Wait orientado a eventos
    4. Relaciona a conta testada ao usuário autenticado (Multi-tenant)
    """
    device = req.device_addr or current_active_adb_device or "127.0.0.1:21503"
    adb_bin = get_adb_cmd()
    
    try:
        temp_dir = os.path.join(BASE_DIR, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        mac = req.mac
        if not mac and req.xml_content:
            m_match = re.search(r'SP_SN_BACKUP">([0-9A-Fa-f:]{17})', req.xml_content) or re.search(r'KEY_SP_SN">([0-9A-Fa-f:]{17})', req.xml_content)
            if m_match:
                mac = m_match.group(1)
        if not mac:
            mac = engine.generate_random_mac()
            
        clean_mac = mac.strip().upper()

        # --- SMART SKIP (INTELIGÊNCIA COLETIVA) ---
        # Se o MAC já existir na tabela AccountHistory e for conhecido como inválido/bloqueado (is_valid = False),
        # NÃO aciona o ADB nem abre o emulador. Retorna imediatamente a falha em cache.
        session = SessionLocal()
        try:
            cached_account = session.query(AccountHistory).filter(
                func.upper(AccountHistory.mac) == clean_mac
            ).first()
            if cached_account and cached_account.is_valid is False:
                skip_reason = cached_account.status_message or "Falha / Banida"
                status_msg = f"⚡ Smart Skip: Conta banida previamente ({skip_reason})"
                return {
                    "success": True,
                    "device": device,
                    "smart_skipped": True,
                    "logs": [
                        f"⚡ [Smart Skip Ativado] O MAC {clean_mac} já foi testado anteriormente e registrado como inválido/bloqueado ({skip_reason}).",
                        "Emulador poupado com sucesso (Economia de tempo e zero re-teste de conta inútil)."
                    ],
                    "account_info": {
                        "found": False,
                        "account_id": cached_account.account_id or "-",
                        "user_id_int": int(cached_account.account_id) if (cached_account.account_id and cached_account.account_id.isdigit()) else 0,
                        "activation_date": "-",
                        "days_active": cached_account.days_active,
                        "expiration_date": "-",
                        "status_message": status_msg,
                        "is_valid": False,
                        "mac": clean_mac,
                        "key_n_bt": "",
                        "folder_name": "CONFIG_ERRO_EF9",
                        "smart_skipped": True
                    }
                }
        finally:
            session.close()

        xml_text = req.xml_content or engine.generate_xml_content(mac=mac)
        temp_xml = os.path.join(temp_dir, "cache.config.xml")
        
        with open(temp_xml, "w", encoding="utf-8") as f:
            f.write(xml_text)
            
        logs = []
        ensure_adb_connected(device)
        logs.append(f"Conectando ao dispositivo ADB: {device}")
        
        # Executa Smart Wipe (Limpeza Inteligente)
        deep_wipe_emulator(device)
        logs.append("Smart Wipe (am force-stop + remoção de backups ocultos) realizado com sucesso")
            
        # Cria diretórios de destino se não existirem
        subprocess.run([adb_bin, "-s", device, "shell", "mkdir -p /sdcard"], capture_output=True, text=True, timeout=10)

        # Injeta exclusivamente o cache.config.xml com a tag SP_SN_BACKUP
        subprocess.run([adb_bin, "-s", device, "push", temp_xml, "/sdcard/cache.config.xml"], capture_output=True, text=True, timeout=10)
        
        # Injeta diretamente em shared_prefs com permissão 666 para cada pacote UniTV
        for pkg in UNITV_PACKAGES:
            subprocess.run([adb_bin, "-s", device, "shell", f"su -c 'mkdir -p /data/data/{pkg}/shared_prefs && cp /sdcard/cache.config.xml /data/data/{pkg}/shared_prefs/cache.config.xml && chmod 666 /data/data/{pkg}/shared_prefs/cache.config.xml'"], capture_output=True, text=True, timeout=5)
        
        logs.append(f"cache.config.xml atualizado com MAC {mac}")
        
        account_info = None
        if req.launch_app:
            grant_all_app_permissions(device)
            for pkg in UNITV_PACKAGES:
                subprocess.run([adb_bin, "-s", device, "shell", f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1"], capture_output=True, text=True, timeout=5)
            logs.append("UniTV Free iniciado no emulador...")
            
            logs.append("Aguardando carregamento da interface (Smart Wait)...")
            account_info = inspect_emulator_account_info(
                device,
                expected_config_content=req.config_content,
                target_mac=mac,
                user_id=current_user.id
            )
            
            if account_info and account_info.get("found"):
                if account_info.get("account_id"):
                    logs.append(f"👑 ID da Conta: {account_info['account_id']}")
                if account_info.get("activation_date"):
                    logs.append(f"📅 Ativada em: {account_info['activation_date']} ({account_info.get('days_active', 0)} dias ativa)")
                if account_info.get("status_message"):
                    logs.append(f"💬 Status: {account_info['status_message']}")
            elif account_info and account_info.get("status_message"):
                logs.append(f"💬 Status: {account_info['status_message']}")
            
        return {
            "success": True,
            "device": device,
            "logs": logs,
            "account_info": account_info
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/adb/account-info")
@app.post("/api/adb/account-info")
def get_account_info_endpoint(
    device_addr: Optional[str] = "127.0.0.1:21503",
    mac: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Endpoint para ler sob demanda os dados e dias ativos da conta no emulador"""
    uid = current_user.id if current_user else None
    return inspect_emulator_account_info(device_addr or "127.0.0.1:21503", target_mac=mac, user_id=uid)

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
    print(f"🚀 Servidor do Gerador Local + Nuvem (10k) & ADB (v1.4.0) iniciado!")
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
