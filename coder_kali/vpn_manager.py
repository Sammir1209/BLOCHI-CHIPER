"""
coder_kali/vpn_manager.py - Gestor Central Multi-VPN y Privacidad (OPSEC) para Blood-Cipher.
Administra conexiones OpenVPN y WireGuard, descarga de perfiles, credenciales seguras
y diagnóstico de fuga de IP pública y salud de conectividad con IAs.
"""

import os
import sys
import time
import shutil
import zipfile
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import requests

from coder_kali.config import CONFIG_DIR

VPN_DIR = CONFIG_DIR / "vpn"
PID_FILE = VPN_DIR / "vpn.pid"
LOG_FILE = VPN_DIR / "vpn.log"
ACTIVE_PROFILE_FILE = VPN_DIR / "active_profile.json"

VPN_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "surfshark": {
        "name": "Surfshark VPN",
        "protocol": "openvpn",
        "auth_type": "service_credentials",
        "config_url": "https://my.surfshark.com/vpn/api/v1/server/configurations",
        "auth_file": "surfshark_auth.txt",
        "popular_locations": [
            ("es-mad", "España (Madrid)", "es-mad.prod.surfshark.com_udp.ovpn"),
            ("es-bcn", "España (Barcelona)", "es-bcn.prod.surfshark.com_udp.ovpn"),
            ("us-nyc", "EE.UU. (New York)", "us-nyc.prod.surfshark.com_udp.ovpn"),
            ("us-mia", "EE.UU. (Miami)", "us-mia.prod.surfshark.com_udp.ovpn"),
            ("us-lax", "EE.UU. (Los Angeles)", "us-lax.prod.surfshark.com_udp.ovpn"),
            ("de-fra", "Alemania (Frankfurt)", "de-fra.prod.surfshark.com_udp.ovpn"),
            ("nl-ams", "Países Bajos (Amsterdam)", "nl-ams.prod.surfshark.com_udp.ovpn"),
            ("ch-zur", "Suiza (Zúrich)", "ch-zur.prod.surfshark.com_udp.ovpn"),
            ("gb-lon", "Reino Unido (Londres)", "gb-lon.prod.surfshark.com_udp.ovpn"),
            ("fr-par", "Francia (París)", "fr-par.prod.surfshark.com_udp.ovpn"),
            ("ca-tor", "Canadá (Toronto)", "ca-tor.prod.surfshark.com_udp.ovpn"),
            ("jp-tok", "Japón (Tokio)", "jp-tok.prod.surfshark.com_udp.ovpn"),
        ],
    },
    "nordvpn": {
        "name": "NordVPN",
        "protocol": "openvpn",
        "auth_type": "service_credentials",
        "config_url": "https://downloads.nordcdn.com/configs/archives/servers/ovpn.zip",
        "auth_file": "nordvpn_auth.txt",
        "popular_locations": [
            ("es", "España (Recomendado)", "es"),
            ("us", "Estados Unidos", "us"),
            ("de", "Alemania", "de"),
            ("nl", "Países Bajos", "nl"),
            ("ch", "Suiza", "ch"),
            ("uk", "Reino Unido", "uk"),
        ],
    },
    "protonvpn": {
        "name": "ProtonVPN",
        "protocol": "openvpn",
        "auth_type": "service_credentials",
        "auth_file": "protonvpn_auth.txt",
        "portal_url": "https://account.protonvpn.com/downloads",
        "popular_locations": [
            ("free", "Servidores Gratuitos Proton (NL / US / JP)", "free"),
            ("plus", "Servidores Plus / Secure Core", "plus"),
        ],
    },
    "mullvad": {
        "name": "Mullvad VPN",
        "protocol": "wireguard",
        "auth_type": "account_number",
        "portal_url": "https://mullvad.net/account",
        "popular_locations": [
            ("se", "Suecia", "se"),
            ("de", "Alemania", "de"),
            ("nl", "Países Bajos", "nl"),
            ("us", "Estados Unidos", "us"),
            ("ch", "Suiza", "ch"),
        ],
    },
    "custom": {
        "name": "VPN Personalizada / Lab (TryHackMe, HTB, VPS)",
        "protocol": "openvpn",
        "auth_type": "embedded_or_credentials",
        "popular_locations": [],
    },
    "tor": {
        "name": "Tor Network (SOCKS5 Local)",
        "protocol": "socks5",
        "auth_type": "none",
        "proxy_address": "socks5://127.0.0.1:9050",
        "control_port": 9051,
    },
}


class VPNManager:
    """Gestiona el ciclo de vida de conexiones VPN, configuración y verificación de IP."""

    def __init__(self):
        self._ensure_vpn_dir()

    def _ensure_vpn_dir(self):
        VPN_DIR.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(VPN_DIR, 0o700)
        except Exception:
            pass

    # ==========================================================================
    # VERIFICACIÓN DE ESTADO Y RED
    # ==========================================================================

    def get_public_ip_info(self, timeout: float = 4.0) -> Dict[str, Any]:
        """Obtiene la IP pública actual y datos de geolocalización."""
        services = [
            ("https://ipinfo.io/json", lambda r: r.json()),
            ("https://api.ipify.org?format=json", lambda r: {"ip": r.json().get("ip", "Desconocida")}),
            ("https://ifconfig.me/all.json", lambda r: {
                "ip": r.json().get("ip_addr"),
                "country": r.json().get("country_code"),
            }),
        ]
        for url, parser in services:
            try:
                res = requests.get(url, timeout=timeout)
                if res.status_code == 200:
                    data = parser(res)
                    if data and "ip" in data:
                        return {
                            "ip": data.get("ip", "Desconocida"),
                            "country": data.get("country", "Desconocido"),
                            "city": data.get("city", ""),
                            "org": data.get("org", data.get("isp", "Desconocido")),
                            "source": url,
                        }
            except Exception:
                continue

        # Fallback a curl simple
        try:
            cmd = subprocess.run(["curl", "-s", "--max-time", "3", "https://ifconfig.me"], capture_output=True, text=True)
            if cmd.returncode == 0 and cmd.stdout.strip():
                return {
                    "ip": cmd.stdout.strip(),
                    "country": "Desconocido",
                    "city": "",
                    "org": "Desconocido",
                    "source": "ifconfig.me (curl)",
                }
        except Exception:
            pass

        return {"ip": "Sin conexión o bloqueada", "country": "-", "city": "", "org": "-"}

    def is_vpn_active(self) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Comprueba si hay una VPN activa.
        Retorna (activo: bool, nombre_interfaz_o_proveedor: str, pid: Optional[int]).
        """
        # 1. Comprobar PID activo registrado
        if PID_FILE.exists():
            try:
                pid = int(PID_FILE.read_text().strip())
                # Comprobar si el proceso sigue vivo
                if sys.platform != "win32":
                    os.kill(pid, 0)
                    return True, "openvpn (daemon)", pid
            except (ValueError, OSError):
                PID_FILE.unlink(missing_ok=True)

        # 2. Comprobar interfaces de red típicas (tun0, wg0, tap0) en Linux
        if sys.platform != "win32":
            try:
                res = subprocess.run(["ip", "link"], capture_output=True, text=True)
                for line in res.stdout.splitlines():
                    for iface in ["tun0", "tun1", "wg0", "wg1", "tap0"]:
                        if iface in line:
                            return True, iface, None
            except Exception:
                pass

        return False, None, None

    def check_ai_health(self) -> Dict[str, bool]:
        """Comprueba conectividad directa con las APIs de IA para verificar que la VPN no las bloquea."""
        endpoints = {
            "Plugsky AI": "https://api.plugsky.com",
            "OpenRouter": "https://openrouter.ai/api/v1/models",
            "Puter AI": "https://api.puter.com",
            "DeepSeek": "https://api.deepseek.com",
            "HuggingFace": "https://huggingface.co",
            "Google Gemini": "https://generativelanguage.googleapis.com",
            "BazaarLink": "https://bazaarlink.ai",
        }
        results = {}
        for name, url in endpoints.items():
            try:
                r = requests.head(url, timeout=4.0, allow_redirects=True)
                results[name] = r.status_code in [200, 301, 302, 401, 403, 404, 405]
            except Exception:
                results[name] = False
        return results

    # ==========================================================================
    # GESTIÓN DE CREDENCIALES
    # ==========================================================================

    def save_credentials(self, provider: str, username: str, password: str) -> Path:
        """Guarda credenciales de servicio en formato OpenVPN seguro (0600)."""
        auth_file = VPN_DIR / f"{provider}_auth.txt"
        content = f"{username.strip()}\n{password.strip()}\n"
        auth_file.write_text(content, encoding="utf-8")
        try:
            os.chmod(auth_file, 0o600)
        except Exception:
            pass
        return auth_file

    def get_credentials(self, provider: str) -> Optional[Tuple[str, str]]:
        """Carga usuario y contraseña guardados para un proveedor."""
        # 1. Mirar en el directorio de la VPN de Blood-Cipher
        auth_file = VPN_DIR / f"{provider}_auth.txt"
        # 2. Mirar en /etc/openvpn/ como fallback si se configuró en el sistema
        sys_file = Path("/etc/openvpn") / f"{provider}_auth.txt"
        
        target = auth_file if auth_file.exists() else (sys_file if sys_file.exists() else None)
        if target and target.exists():
            try:
                lines = [l.strip() for l in target.read_text(encoding="utf-8").splitlines() if l.strip()]
                if len(lines) >= 2:
                    return lines[0], lines[1]
            except Exception:
                pass
        return None

    # ==========================================================================
    # DESCARGA Y CONFIGURACIONES
    # ==========================================================================

    def get_provider_configs_dir(self, provider: str) -> Path:
        pdir = VPN_DIR / provider
        pdir.mkdir(parents=True, exist_ok=True)
        return pdir

    def download_provider_configs(self, provider: str) -> Tuple[bool, str]:
        """Descarga y extrae los perfiles .ovpn oficiales del proveedor."""
        meta = VPN_PROVIDERS.get(provider)
        if not meta or "config_url" not in meta:
            return False, f"El proveedor {provider} no admite descarga automatizada de perfiles."

        url = meta["config_url"]
        target_dir = self.get_provider_configs_dir(provider)
        zip_path = target_dir / f"{provider}_configs.zip"

        try:
            res = requests.get(url, timeout=30, stream=True)
            if res.status_code != 200:
                return False, f"Error HTTP {res.status_code} al descargar configuraciones."

            with open(zip_path, "wb") as f:
                for chunk in res.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Extraer archivos
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(target_dir)

            zip_path.unlink(missing_ok=True)
            ovpn_count = len(list(target_dir.glob("**/*.ovpn")))
            return True, f"Se descargaron y extrajeron {ovpn_count} perfiles .ovpn para {meta['name']}."
        except Exception as e:
            return False, f"Fallo al descargar configuraciones: {e}"

    def list_available_ovpn_files(self, provider: str) -> List[Path]:
        """Devuelve todos los archivos .ovpn disponibles localmente para el proveedor."""
        # 1. En carpeta local de Blood-Cipher
        target_dir = self.get_provider_configs_dir(provider)
        local_files = list(target_dir.glob("**/*.ovpn"))
        if local_files:
            return sorted(local_files, key=lambda p: p.name)

        # 2. En /etc/openvpn/
        sys_dir = Path("/etc/openvpn")
        if sys_dir.exists():
            sys_files = list(sys_dir.glob("*.ovpn"))
            if sys_files:
                return sorted(sys_files, key=lambda p: p.name)

        return []

    def find_ovpn_for_location(self, provider: str, location_code: str) -> Optional[Path]:
        """Busca el archivo .ovpn correspondiente a un código de país o ciudad."""
        files = self.list_available_ovpn_files(provider)
        location_lower = location_code.lower().strip()

        # Búsqueda con coincidencia exacta y UDP
        for f in files:
            if location_lower in f.name.lower() and "_udp" in f.name.lower():
                return f
        for f in files:
            if location_lower in f.name.lower():
                return f
        return files[0] if files else None

    # ==========================================================================
    # CONEXIÓN Y DESCONEXIÓN
    # ==========================================================================

    def connect(
        self,
        provider: str,
        config_path: Optional[str] = None,
        location_code: Optional[str] = None,
        daemon: bool = True,
    ) -> Tuple[bool, str]:
        """Inicia una conexión VPN con el proveedor indicado."""
        if sys.platform == "win32":
            return False, "La gestión de OpenVPN en segundo plano está optimizada para Linux/Kali/Debian/Arch. En Windows ejecuta tu cliente Surfshark/VPN oficial."

        # Comprobar si ya está activa
        active, iface, pid = self.is_vpn_active()
        if active:
            return False, f"Ya hay una VPN activa en el sistema ({iface} - PID: {pid}). Ejecuta 'blood-cipher vpn disconnect' primero."

        # Comprobar ejecutable openvpn
        if not shutil.which("openvpn"):
            return False, "OpenVPN no está instalado en el sistema. Ejecuta: 'sudo apt install -y openvpn'."

        # Resolver archivo .ovpn
        ovpn_file: Optional[Path] = None
        if config_path:
            ovpn_file = Path(config_path)
            if not ovpn_file.exists():
                return False, f"El archivo de configuración '{config_path}' no existe."
        elif provider in VPN_PROVIDERS:
            # Si no hay archivos, intentar descargarlos si el proveedor lo soporta
            existing = self.list_available_ovpn_files(provider)
            if not existing and "config_url" in VPN_PROVIDERS[provider]:
                self.download_provider_configs(provider)
                existing = self.list_available_ovpn_files(provider)

            if location_code:
                ovpn_file = self.find_ovpn_for_location(provider, location_code)
            elif existing:
                ovpn_file = existing[0]

        if not ovpn_file or not ovpn_file.exists():
            return False, f"No se encontró un perfil .ovpn para {provider}. Descarga las configuraciones o proporciona la ruta al archivo."

        # Resolver credenciales
        creds = self.get_credentials(provider)
        auth_file = VPN_DIR / f"{provider}_auth.txt"
        if not auth_file.exists() and creds:
            auth_file = self.save_credentials(provider, creds[0], creds[1])

        # Construir comando
        cmd = ["openvpn", "--config", str(ovpn_file.resolve())]
        if auth_file.exists():
            cmd.extend(["--auth-user-pass", str(auth_file.resolve())])

        if daemon:
            cmd.extend(["--daemon", "--writepid", str(PID_FILE.resolve()), "--log", str(LOG_FILE.resolve())])

        # En Linux requiere privilegios de root para crear interfaz tun
        if os.geteuid() != 0:
            cmd.insert(0, "sudo")

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if proc.returncode != 0:
                return False, f"Error al iniciar OpenVPN: {proc.stderr or proc.stdout}"

            # Guardar perfil activo
            ACTIVE_PROFILE_FILE.write_text(
                f'{{"provider": "{provider}", "config": "{ovpn_file.name}", "timestamp": {time.time()}}}',
                encoding="utf-8",
            )

            # Dar 3 segundos para que se levante la interfaz
            time.sleep(3)

            # Verificar IP resultante
            new_ip_info = self.get_public_ip_info(timeout=5.0)
            return True, f"¡VPN conectada con éxito a {ovpn_file.name}! IP Pública actual: {new_ip_info.get('ip')} ({new_ip_info.get('country')})"
        except Exception as e:
            return False, f"Excepción al ejecutar OpenVPN: {e}"

    def disconnect(self) -> Tuple[bool, str]:
        """Detiene cualquier proceso OpenVPN activo en el sistema."""
        killed = False

        # 1. Por PID registrado
        if PID_FILE.exists():
            try:
                pid = int(PID_FILE.read_text().strip())
                cmd = ["kill", "-15", str(pid)] if os.geteuid() == 0 else ["sudo", "kill", "-15", str(pid)]
                subprocess.run(cmd, capture_output=True)
                killed = True
            except Exception:
                pass
            finally:
                PID_FILE.unlink(missing_ok=True)

        # 2. Por pkill general de openvpn
        try:
            cmd = ["killall", "openvpn"] if os.geteuid() == 0 else ["sudo", "killall", "openvpn"]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                killed = True
        except Exception:
            pass

        ACTIVE_PROFILE_FILE.unlink(missing_ok=True)

        # Dar 1 segundo y comprobar IP
        time.sleep(1)
        ip_info = self.get_public_ip_info(timeout=4.0)

        if killed:
            return True, f"VPN desconectada exitosamente. IP Pública restaurada: {ip_info.get('ip')} ({ip_info.get('country')})"
        else:
            return True, f"No se detectaron procesos OpenVPN en ejecución. IP Pública actual: {ip_info.get('ip')}"
