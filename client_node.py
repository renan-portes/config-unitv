"""
Scanner Node - Aplicativo Desktop Cliente (Worker GUI)
Gerador e Validador de Configurações IPTV
Interface Gráfica com customtkinter e Trava de Hardware ID (HWID)
"""

import os
import sys
import uuid
import hashlib
import subprocess
import threading
import requests
import customtkinter as ctk
from typing import Optional


def get_hwid() -> str:
    """
    Obtém um identificador único de hardware (HWID) da máquina local.
    Prioriza o UUID da placa-mãe/BIOS no Windows (PowerShell/CIM/wmic),
    machine-id no Linux ou IOPlatformUUID no macOS, com fallback para uuid.getnode().
    Retorna uma string hexadecimal de 32 caracteres (SHA-256).
    """
    try:
        if sys.platform == "win32":
            # 1. Tenta PowerShell CIM Instance
            try:
                cmd = ["powershell", "-NoProfile", "-Command", "(Get-CimInstance -Class Win32_ComputerSystemProduct).UUID"]
                output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=3).decode().strip()
                if output and len(output) > 8 and "FFFFFFFF" not in output.upper():
                    return hashlib.sha256(output.encode("utf-8")).hexdigest()[:32].upper()
            except Exception:
                pass

            # 2. Tenta comando WMIC clássico
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

    # Fallback seguro baseado em MAC address da interface física
    node_id = str(uuid.getnode())
    return hashlib.sha256(f"HWID-FALLBACK-{node_id}".encode("utf-8")).hexdigest()[:32].upper()


class ScannerNodeApp(ctk.CTk):
    """Interface Gráfica do Aplicativo Cliente / Worker Node"""

    def __init__(self):
        super().__init__()

        # Configurações gerais da janela
        self.title("Scanner Node - Cliente de Validação IPTV")
        self.geometry("520x680")
        self.minsize(480, 620)
        self.resizable(True, True)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Estado da Sessão
        self.hwid = get_hwid()
        self.auth_token: Optional[str] = None
        self.user_data: Optional[dict] = None
        self.is_connecting = False

        self._build_ui()

    def _build_ui(self):
        """Monta a interface moderna com customtkinter"""
        # Container principal com padding
        self.main_frame = ctk.CTkFrame(self, corner_radius=16, fg_color="#111827", border_width=1, border_color="#1f2937")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Cabeçalho / Banner
        self.header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=20, pady=(20, 10))

        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text="⚡ Scanner Node",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#f3f4f6"
        )
        self.title_label.pack(anchor="w")

        self.subtitle_label = ctk.CTkLabel(
            self.header_frame,
            text="Cliente de Autenticação e Validação Distribuída",
            font=ctk.CTkFont(size=12),
            text_color="#9ca3af"
        )
        self.subtitle_label.pack(anchor="w", pady=(2, 0))

        # Card de HWID Detectado
        self.hwid_card = ctk.CTkFrame(self.main_frame, corner_radius=10, fg_color="#1f2937", border_width=1, border_color="#374151")
        self.hwid_card.pack(fill="x", padx=20, pady=10)

        self.hwid_header = ctk.CTkLabel(
            self.hwid_card,
            text="🔒 ID do Computador (Hardware ID - HWID):",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#60a5fa"
        )
        self.hwid_header.pack(anchor="w", padx=12, pady=(8, 2))

        self.hwid_val_label = ctk.CTkLabel(
            self.hwid_card,
            text=self.hwid,
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#e5e7eb"
        )
        self.hwid_val_label.pack(anchor="w", padx=12, pady=(0, 8))

        # Formulário de Conexão
        self.form_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.form_frame.pack(fill="x", padx=20, pady=10)

        # Servidor Master API
        self.server_lbl = ctk.CTkLabel(self.form_frame, text="Servidor Master API:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#d1d5db")
        self.server_lbl.pack(anchor="w", pady=(5, 2))

        self.server_entry = ctk.CTkEntry(
            self.form_frame,
            placeholder_text="http://127.0.0.1:8000",
            font=ctk.CTkFont(size=12),
            height=38,
            corner_radius=8,
            border_color="#374151",
            fg_color="#1f2937"
        )
        self.server_entry.insert(0, "http://127.0.0.1:8000")
        self.server_entry.pack(fill="x", pady=(0, 10))

        # Usuário
        self.user_lbl = ctk.CTkLabel(self.form_frame, text="Nome de Usuário:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#d1d5db")
        self.user_lbl.pack(anchor="w", pady=(5, 2))

        self.user_entry = ctk.CTkEntry(
            self.form_frame,
            placeholder_text="Digite seu usuário",
            font=ctk.CTkFont(size=12),
            height=38,
            corner_radius=8,
            border_color="#374151",
            fg_color="#1f2937"
        )
        self.user_entry.pack(fill="x", pady=(0, 10))

        # Senha
        self.pass_lbl = ctk.CTkLabel(self.form_frame, text="Senha de Acesso:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#d1d5db")
        self.pass_lbl.pack(anchor="w", pady=(5, 2))

        self.pass_entry = ctk.CTkEntry(
            self.form_frame,
            placeholder_text="••••••••",
            show="*",
            font=ctk.CTkFont(size=12),
            height=38,
            corner_radius=8,
            border_color="#374151",
            fg_color="#1f2937"
        )
        self.pass_entry.pack(fill="x", pady=(0, 15))

        # Botão Conectar
        self.connect_btn = ctk.CTkButton(
            self.form_frame,
            text="Conectar ao Master",
            command=self.on_connect_clicked,
            font=ctk.CTkFont(size=13, weight="bold"),
            height=42,
            corner_radius=10,
            fg_color="#7c3aed",
            hover_color="#6d28d9"
        )
        self.connect_btn.pack(fill="x", pady=(5, 10))

        # Card de Status / Feedback
        self.status_card = ctk.CTkFrame(self.main_frame, corner_radius=10, fg_color="#1f2937", border_width=1, border_color="#374151")
        self.status_card.pack(fill="both", expand=True, padx=20, pady=(10, 20))

        self.status_title = ctk.CTkLabel(
            self.status_card,
            text="Status da Conexão:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#9ca3af"
        )
        self.status_title.pack(anchor="w", padx=12, pady=(10, 2))

        self.status_msg = ctk.CTkLabel(
            self.status_card,
            text="Pronto para autenticar com o servidor Master.",
            font=ctk.CTkFont(size=12),
            text_color="#d1d5db",
            wraplength=420,
            justify="left"
        )
        self.status_msg.pack(anchor="w", padx=12, pady=(0, 10))

    def set_status(self, message: str, status_type: str = "info"):
        """Atualiza a mensagem e cor do card de status"""
        color_map = {
            "info": ("#9ca3af", "#d1d5db", "#374151"),
            "success": ("#34d399", "#a7f3d0", "#065f46"),
            "error": ("#f87171", "#fecaca", "#991b1b"),
            "warning": ("#fbbf24", "#fef3c7", "#92400e"),
        }
        title_color, msg_color, border_color = color_map.get(status_type, color_map["info"])

        self.status_title.configure(text_color=title_color)
        self.status_msg.configure(text=message, text_color=msg_color)
        self.status_card.configure(border_color=border_color)

    def on_connect_clicked(self):
        """Handler do clique do botão Conectar (dispara thread)"""
        if self.is_connecting:
            return

        server_url = self.server_entry.get().strip().rstrip("/")
        username = self.user_entry.get().strip()
        password = self.pass_entry.get().strip()

        if not server_url:
            self.set_status("Informe a URL do servidor Master API.", "error")
            return
        if not username or not password:
            self.set_status("Preencha usuário e senha para conectar.", "error")
            return

        self.is_connecting = True
        self.connect_btn.configure(state="disabled", text="Autenticando...")
        self.set_status("Conectando ao servidor e validando Hardware ID...", "info")

        # Executa a requisição em thread separada para não congelar a GUI
        threading.Thread(
            target=self._perform_login_request,
            args=(server_url, username, password),
            daemon=True
        ).start()

    def _perform_login_request(self, server_url: str, username: str, password: str):
        """Executa a requisição HTTP POST para o endpoint de login"""
        endpoint = f"{server_url}/api/auth/login"
        payload = {
            "username": username,
            "password": password,
            "hwid": self.hwid
        }

        try:
            resp = requests.post(endpoint, json=payload, timeout=8)
            status_code = resp.status_code

            try:
                data = resp.json()
            except Exception:
                data = {}

            # Atualiza GUI na thread principal
            self.after(0, self._handle_login_response, status_code, data)

        except requests.exceptions.ConnectionError:
            self.after(
                0,
                self.set_status,
                f"❌ Falha de Conexão: Não foi possível conectar ao servidor Master em '{server_url}'. Verifique se o servidor está online.",
                "error"
            )
            self.after(0, self._reset_connect_button)
        except requests.exceptions.Timeout:
            self.after(
                0,
                self.set_status,
                "⏱️ Tempo Limite Esgotado: O servidor demorou muito para responder.",
                "error"
            )
            self.after(0, self._reset_connect_button)
        except Exception as e:
            self.after(
                0,
                self.set_status,
                f"❌ Erro inesperado: {str(e)}",
                "error"
            )
            self.after(0, self._reset_connect_button)

    def _handle_login_response(self, status_code: int, data: dict):
        """Processa a resposta HTTP do login"""
        self._reset_connect_button()

        if status_code == 200:
            self.auth_token = data.get("access_token")
            self.user_data = data.get("user", {})
            user_name = self.user_data.get("username", "Usuário")
            user_role = self.user_data.get("role", "user")

            expiry_text = "Vitalício"
            if self.user_data.get("expires_at"):
                expiry_text = self.user_data.get("expires_at")

            msg = (
                f"✅ Conectado com Sucesso!\n\n"
                f"• Usuário: {user_name} ({user_role.upper()})\n"
                f"• Assinatura: {expiry_text}\n"
                f"• HWID Vinculado: {self.hwid[:12]}...\n"
                f"• Sessão Token: JWT Ativo"
            )
            self.set_status(msg, "success")

        elif status_code == 401:
            detail = data.get("detail", "Usuário ou senha incorretos.")
            self.set_status(f"❌ Falha de Autenticação: {detail}", "error")

        elif status_code == 403:
            detail = data.get("detail", "Acesso Proibido.")
            if "vinculado a outro computador" in detail.lower():
                self.set_status(
                    f"🚫 Bloqueado por HWID:\n{detail}\n\nEntre em contato com o Administrador para resetar a vinculação do seu computador.",
                    "error"
                )
            elif "expirada" in detail.lower():
                self.set_status(
                    f"⏳ Assinatura Expirada:\n{detail}",
                    "warning"
                )
            else:
                self.set_status(f"🚫 Acesso Negado: {detail}", "error")

        else:
            detail = data.get("detail", f"Erro HTTP {status_code}")
            self.set_status(f"❌ Erro do Servidor: {detail}", "error")

    def _reset_connect_button(self):
        """Restaura o estado do botão Conectar"""
        self.is_connecting = False
        self.connect_btn.configure(state="normal", text="Conectar ao Master")


if __name__ == "__main__":
    app = ScannerNodeApp()
    app.mainloop()
