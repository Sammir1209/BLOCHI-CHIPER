"""
coder_kali/mcp_hub.py - MCP Security Hub: Registro Modular de Herramientas de Seguridad.

Implementa un sistema inspirado en el Model Context Protocol (MCP) para registrar,
descubrir y ejecutar herramientas de seguridad de forma modular.

Cada herramienta tiene:
- Nombre y descripción
- Esquema de parámetros con valores por defecto optimizados
- Template de comando con placeholders
- Auto-detección de instalación (which/shutil.which)
- Comando de instalación automática como fallback
"""

import shutil
import platform
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class ToolParam:
    """Parámetro individual de una herramienta de seguridad."""
    name: str
    description: str
    required: bool = False
    default: Optional[str] = None
    param_type: str = "string"  # string, int, bool, list


@dataclass 
class SecurityTool:
    """Definición completa de una herramienta de seguridad registrada."""
    name: str
    category: str  # recon, exploit, vuln_scan, brute_force, osint, web, crypto
    description: str
    binary_name: str  # Nombre del ejecutable (ej: 'nmap', 'sqlmap')
    params: List[ToolParam] = field(default_factory=list)
    template: str = ""  # Template de comando con {placeholders}
    install_cmd: str = ""  # Comando para instalar si no existe
    alt_binary: Optional[str] = None  # Binario alternativo (ej: httpx-toolkit vs httpx)
    is_installed: bool = False
    binary_path: Optional[str] = None


# ─── Registro Global de Herramientas ───────────────────────────────────────────

TOOL_REGISTRY: Dict[str, SecurityTool] = {}


def _register_builtin_tools():
    """Registra todas las herramientas de seguridad built-in del sistema."""
    
    tools = [
        # ── RECONOCIMIENTO ──────────────────────────────────────────
        SecurityTool(
            name="nmap",
            category="recon",
            description="Escáner de puertos, servicios y detección de SO",
            binary_name="nmap",
            params=[
                ToolParam("target", "IP, hostname o rango CIDR a escanear", required=True),
                ToolParam("ports", "Puertos a escanear (ej: 80,443 o 1-1000)", default="--top-ports 1000"),
                ToolParam("scan_type", "Tipo de escaneo: -sS (SYN), -sV (versiones), -sC (scripts)", default="-sS -sV"),
                ToolParam("speed", "Velocidad T0-T5", default="-T4"),
                ToolParam("timeout", "Timeout por host", default="--host-timeout 3m"),
                ToolParam("output", "Formato de salida: -oN, -oX, -oG, -oA", default="-oN"),
            ],
            template="nmap {scan_type} {speed} {ports} {timeout} {target} -o {output}",
            install_cmd="sudo apt install -y nmap",
        ),
        SecurityTool(
            name="subfinder",
            category="osint",
            description="Descubrimiento pasivo de subdominios",
            binary_name="subfinder",
            params=[
                ToolParam("domain", "Dominio objetivo", required=True),
                ToolParam("output", "Archivo de salida", default="subdomains.txt"),
                ToolParam("silent", "Modo silencioso", default="-silent"),
            ],
            template="subfinder -d {domain} {silent} -o {output}",
            install_cmd="sudo apt install -y subfinder || go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest",
        ),
        SecurityTool(
            name="httpx",
            category="recon",
            description="Sondeo HTTP masivo con detección de tecnologías",
            binary_name="httpx-toolkit",
            alt_binary="httpx",
            params=[
                ToolParam("input", "Archivo de entrada con URLs/dominios", required=True),
                ToolParam("probes", "Opciones de sondeo", default="-status-code -title -tech-detect -follow-redirects"),
                ToolParam("output", "Archivo de salida JSON", default="httpx_results.json"),
                ToolParam("threads", "Hilos concurrentes", default="-t 50"),
                ToolParam("timeout", "Timeout por request", default="-timeout 5"),
            ],
            template="cat {input} | httpx-toolkit {probes} {threads} {timeout} -json -o {output}",
            install_cmd="sudo apt install -y httpx-toolkit",
        ),
        SecurityTool(
            name="whatweb",
            category="recon",
            description="Fingerprinting de tecnologías web",
            binary_name="whatweb",
            params=[
                ToolParam("target", "URL objetivo", required=True),
                ToolParam("aggression", "Nivel de agresividad 1-4", default="-a 3"),
                ToolParam("verbose", "Verbose output", default="-v"),
            ],
            template="whatweb {target} {aggression} {verbose}",
            install_cmd="sudo apt install -y whatweb",
        ),

        # ── VULNERABILIDADES ────────────────────────────────────────
        SecurityTool(
            name="nuclei",
            category="vuln_scan",
            description="Escáner de vulnerabilidades basado en templates",
            binary_name="nuclei",
            params=[
                ToolParam("target", "URL o archivo de objetivos", required=True),
                ToolParam("severity", "Severidades a buscar", default="-severity high,critical"),
                ToolParam("rate_limit", "Rate limit de requests", default="-rl 150"),
                ToolParam("timeout", "Timeout por request", default="-timeout 5"),
                ToolParam("output", "Archivo de salida", default="nuclei_findings.json"),
            ],
            template="nuclei -u {target} {severity} {rate_limit} {timeout} -j -o {output}",
            install_cmd="sudo apt install -y nuclei || go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest",
        ),
        SecurityTool(
            name="wpscan",
            category="vuln_scan",
            description="Escáner de vulnerabilidades para WordPress",
            binary_name="wpscan",
            params=[
                ToolParam("url", "URL del sitio WordPress", required=True),
                ToolParam("enumerate", "Elementos a enumerar: u,vp,vt,p,t", default="--enumerate u,vp"),
                ToolParam("api_token", "API token de WPScan (opcional)", default=""),
            ],
            template="wpscan --url {url} {enumerate} --random-user-agent",
            install_cmd="sudo apt install -y wpscan",
        ),
        SecurityTool(
            name="nikto",
            category="vuln_scan",
            description="Escáner de vulnerabilidades web clásico",
            binary_name="nikto",
            params=[
                ToolParam("host", "Host objetivo", required=True),
                ToolParam("port", "Puerto", default="-p 80"),
                ToolParam("output", "Archivo de salida", default="-o nikto_report.txt"),
            ],
            template="nikto -h {host} {port} {output}",
            install_cmd="sudo apt install -y nikto",
        ),

        # ── EXPLOTACIÓN ─────────────────────────────────────────────
        SecurityTool(
            name="sqlmap",
            category="exploit",
            description="Herramienta automatizada de inyección SQL",
            binary_name="sqlmap",
            params=[
                ToolParam("url", "URL con parámetro inyectable", required=True),
                ToolParam("batch", "Modo no interactivo", default="--batch"),
                ToolParam("threads", "Hilos de ejecución", default="--threads=10"),
                ToolParam("time_sec", "Tiempo de espera para time-based", default="--time-sec=3"),
                ToolParam("random_agent", "User-Agent aleatorio", default="--random-agent"),
                ToolParam("action", "Acción: --dbs, --tables, --dump", default="--dbs"),
            ],
            template='sqlmap -u "{url}" {batch} {threads} {time_sec} {random_agent} {action}',
            install_cmd="sudo apt install -y sqlmap",
        ),

        # ── FUERZA BRUTA ────────────────────────────────────────────
        SecurityTool(
            name="hydra",
            category="brute_force",
            description="Fuerza bruta de credenciales multi-protocolo",
            binary_name="hydra",
            params=[
                ToolParam("target", "Host objetivo", required=True),
                ToolParam("service", "Servicio: ssh, ftp, http-post-form, etc.", required=True),
                ToolParam("userlist", "Archivo de usuarios", default="-L /usr/share/wordlists/seclists/Usernames/top-usernames-shortlist.txt"),
                ToolParam("passlist", "Archivo de contraseñas", default="-P /usr/share/wordlists/rockyou.txt"),
                ToolParam("threads", "Hilos paralelos", default="-t 16"),
            ],
            template="hydra {target} {service} {userlist} {passlist} {threads} -V",
            install_cmd="sudo apt install -y hydra",
        ),
        SecurityTool(
            name="john",
            category="brute_force",
            description="Cracking de hashes con John the Ripper",
            binary_name="john",
            params=[
                ToolParam("hash_file", "Archivo con hashes", required=True),
                ToolParam("wordlist", "Diccionario", default="--wordlist=/usr/share/wordlists/rockyou.txt"),
                ToolParam("format", "Formato de hash (auto si no se especifica)", default=""),
            ],
            template="john {hash_file} {wordlist} {format}",
            install_cmd="sudo apt install -y john",
        ),

        # ── FUZZING WEB ─────────────────────────────────────────────
        SecurityTool(
            name="ffuf",
            category="web",
            description="Fuzzing ultrarrápido de rutas, parámetros y subdominios",
            binary_name="ffuf",
            params=[
                ToolParam("url", "URL con FUZZ como placeholder", required=True),
                ToolParam("wordlist", "Wordlist para fuzzing", default="-w /usr/share/wordlists/dirb/common.txt"),
                ToolParam("match_codes", "Códigos HTTP a mostrar", default="-mc 200,301,302,403"),
                ToolParam("threads", "Hilos concurrentes", default="-t 80"),
                ToolParam("timeout", "Timeout", default="-timeout 5"),
            ],
            template='ffuf -c {wordlist} -u "{url}" {match_codes} {threads} {timeout}',
            install_cmd="sudo apt install -y ffuf",
        ),
        SecurityTool(
            name="gobuster",
            category="web",
            description="Fuerza bruta de directorios y subdominios",
            binary_name="gobuster",
            params=[
                ToolParam("mode", "Modo: dir, dns, vhost, fuzz", default="dir"),
                ToolParam("url", "URL objetivo", required=True),
                ToolParam("wordlist", "Wordlist", default="-w /usr/share/wordlists/dirb/common.txt"),
                ToolParam("threads", "Hilos", default="-t 50"),
            ],
            template="gobuster {mode} -u {url} {wordlist} {threads}",
            install_cmd="sudo apt install -y gobuster",
        ),

        # ── OSINT ───────────────────────────────────────────────────
        SecurityTool(
            name="theharvester",
            category="osint",
            description="Recolección de emails, subdominios y hosts de fuentes públicas",
            binary_name="theHarvester",
            alt_binary="theharvester",
            params=[
                ToolParam("domain", "Dominio objetivo", required=True),
                ToolParam("source", "Fuente de datos", default="-b all"),
                ToolParam("limit", "Límite de resultados", default="-l 500"),
            ],
            template="theHarvester -d {domain} {source} {limit}",
            install_cmd="sudo apt install -y theharvester",
        ),
    ]

    for tool in tools:
        TOOL_REGISTRY[tool.name] = tool


class MCPSecurityHub:
    """
    Hub central de herramientas de seguridad con auto-detección y registro modular.
    
    Funcionalidades:
    - Auto-detecta herramientas instaladas en el sistema
    - Proporciona esquemas de parámetros al agente
    - Genera comandos optimizados con flags por defecto
    - Sugiere instalación automática de herramientas faltantes
    """

    def __init__(self):
        # Registrar herramientas built-in si no están cargadas
        if not TOOL_REGISTRY:
            _register_builtin_tools()
        
        self.tools = TOOL_REGISTRY
        self._scan_installed()

    def _scan_installed(self):
        """Escanea el sistema para detectar qué herramientas están instaladas."""
        is_linux = platform.system().lower() == "linux"
        
        for name, tool in self.tools.items():
            # Buscar el binario principal
            path = shutil.which(tool.binary_name)
            if not path and tool.alt_binary:
                path = shutil.which(tool.alt_binary)
            
            tool.is_installed = path is not None
            tool.binary_path = path

    def get_installed_tools(self) -> List[SecurityTool]:
        """Retorna solo las herramientas que están instaladas."""
        return [t for t in self.tools.values() if t.is_installed]

    def get_missing_tools(self) -> List[SecurityTool]:
        """Retorna herramientas que NO están instaladas."""
        return [t for t in self.tools.values() if not t.is_installed]

    def get_tool(self, name: str) -> Optional[SecurityTool]:
        """Busca una herramienta por nombre."""
        return self.tools.get(name.lower())

    def get_tools_by_category(self, category: str) -> List[SecurityTool]:
        """Retorna herramientas de una categoría específica."""
        return [t for t in self.tools.values() if t.category == category]

    def get_install_commands(self, tool_names: Optional[List[str]] = None) -> str:
        """
        Genera un bloque de comandos para instalar herramientas faltantes.
        Si no se especifican nombres, instala TODAS las faltantes.
        """
        if tool_names:
            targets = [self.tools[n] for n in tool_names if n in self.tools and not self.tools[n].is_installed]
        else:
            targets = self.get_missing_tools()

        if not targets:
            return "# Todas las herramientas ya están instaladas ✓"

        commands = ["#!/bin/bash", "# Auto-instalación de herramientas de seguridad faltantes", "set -e", ""]
        for tool in targets:
            if tool.install_cmd:
                commands.append(f"echo '[+] Instalando {tool.name}...'")
                commands.append(tool.install_cmd)
                commands.append("")

        return "\n".join(commands)

    def generate_tool_context_for_agent(self) -> str:
        """
        Genera un contexto compacto de herramientas disponibles para inyectar
        en el system prompt del agente.
        """
        installed = self.get_installed_tools()
        missing = self.get_missing_tools()

        lines = ["[MCP SECURITY HUB — ARSENAL DISPONIBLE]"]
        
        if installed:
            lines.append(f"Herramientas instaladas ({len(installed)}):")
            for t in installed:
                params_str = ", ".join(
                    f"{p.name}{'*' if p.required else ''}" for p in t.params[:4]
                )
                lines.append(f"  ✓ {t.name} ({t.category}) — {t.description} [{params_str}]")

        if missing:
            lines.append(f"\nHerramientas NO instaladas ({len(missing)}):")
            for t in missing:
                lines.append(f"  ✗ {t.name} — Instalar con: {t.install_cmd}")

        return "\n".join(lines)

    def register_custom_tool(self, tool: SecurityTool):
        """Registra una herramienta personalizada en el hub."""
        path = shutil.which(tool.binary_name)
        if not path and tool.alt_binary:
            path = shutil.which(tool.alt_binary)
        tool.is_installed = path is not None
        tool.binary_path = path
        self.tools[tool.name] = tool

    def refresh(self):
        """Re-escanea el sistema para actualizar el estado de instalación."""
        self._scan_installed()

    def get_status_summary(self) -> Dict[str, Any]:
        """Retorna resumen del estado del hub para diagnóstico."""
        installed = self.get_installed_tools()
        missing = self.get_missing_tools()
        categories = {}
        for t in self.tools.values():
            cat = t.category
            if cat not in categories:
                categories[cat] = {"installed": 0, "missing": 0}
            if t.is_installed:
                categories[cat]["installed"] += 1
            else:
                categories[cat]["missing"] += 1

        return {
            "total_tools": len(self.tools),
            "installed": len(installed),
            "missing": len(missing),
            "categories": categories,
        }

    @property
    def registry(self) -> Dict[str, SecurityTool]:
        """Alias para self.tools compatible con consultas de registro."""
        return self.tools



# Inicializar registro al importar
_register_builtin_tools()
