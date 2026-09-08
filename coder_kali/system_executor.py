"""
coder_kali/system_executor.py - Ejecutor Seguro de Comandos del Sistema y Gestor PTY.
Interpreta etiquetas XML <ejecutar_comando> y <escribir_archivo ruta="...">,
solicita confirmación al operador y ejecuta en terminal segura / PTY interactivo.
"""

import os
import re
import sys
import subprocess
import platform
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.syntax import Syntax
from rich.text import Text

import shutil
import tempfile

console = Console()

COMMAND_REGEX = re.compile(r"<ejecutar_comando>(.*?)</ejecutar_comando>", re.DOTALL | re.IGNORECASE)
FILE_REGEX = re.compile(
    r'<escribir_archivo\s+ruta=(?:"([^"]+)"|\'([^\']+)\'|([^\s>]+))>(.*?)</escribir_archivo>',
    re.DOTALL | re.IGNORECASE,
)

# Comandos de alto riesgo que requieren advertencia especial
CRITICAL_PATTERNS = [
    r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+(?:/[a-zA-Z0-9_\.]*\s*$|/\s*$|/\*)",  # rm -rf / o rm -rf /*
    r"\bmkfs\b",
    r"\bdd\s+if=.*of=/dev/sd",
    r">\s*/dev/sd[a-z]",
    r":\(\)\{\s*:\|:&\s*\};:",  # fork bomb
    r"\bchmod\s+-R\s+777\s+/(?:$|\s)",
    r"\bchown\s+-R\s+.*?\s+/(?:$|\s)",
]


@dataclass
class ParsedAction:
    action_type: str  # 'command' | 'file'
    content: str
    target_path: Optional[str] = None
    is_sudo: bool = False
    is_dangerous: bool = False


@dataclass
class ExecutionResult:
    success: bool
    output: str
    returncode: int
    command: Optional[str] = None
    target_path: Optional[str] = None
    was_rejected: bool = False
    is_file_op: bool = False


class SystemExecutor:
    """Ejecutor seguro de acciones del sistema con confirmación y PTY interactivo."""

    def __init__(self, auto_approve_safe: bool = False):
        self.auto_approve_safe = auto_approve_safe
        self.os_type = platform.system().lower()
        self.is_linux = self.os_type == "linux"
        self.is_windows = self.os_type == "windows"
        self.is_darwin = self.os_type == "darwin"
        # Detección inteligente de Termux / Android
        self.is_termux = bool(
            os.environ.get("TERMUX_VERSION")
            or os.environ.get("PREFIX", "").startswith("/data/data/com.termux")
            or Path("/data/data/com.termux").exists()
        )
        self.shell_path = self._resolve_shell_path()

    def _resolve_shell_path(self) -> str:
        """Determina la ruta absoluta del shell Bash o Shell nativo según la plataforma."""
        if self.is_windows:
            return "powershell"
        if self.is_termux:
            termux_bash = os.environ.get("PREFIX", "/data/data/com.termux/files/usr") + "/bin/bash"
            if os.path.exists(termux_bash):
                return termux_bash
            termux_sh = os.environ.get("PREFIX", "/data/data/com.termux/files/usr") + "/bin/sh"
            if os.path.exists(termux_sh):
                return termux_sh
        which_bash = shutil.which("bash")
        if which_bash:
            return which_bash
        if os.path.exists("/bin/bash"):
            return "/bin/bash"
        return shutil.which("sh") or "/bin/sh"

    def parse_actions(self, text: str) -> List[ParsedAction]:
        """Extrae todas las acciones (XML o JSON) en el texto de la IA, priorizando la creación de archivos antes de ejecutar comandos."""
        actions: List[ParsedAction] = []
        file_actions: List[ParsedAction] = []
        cmd_actions: List[ParsedAction] = []
        seen_commands = set()

        # Limpiar texto de bloques de pensamiento que puedan tener XML falso o comillas abiertas
        cleaned_text = re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.IGNORECASE)
        cleaned_text = re.sub(r'```(?:thought|thinking|reasoning)[\s\S]*?```', '', cleaned_text, flags=re.IGNORECASE)

        # 1. Buscar creación de archivos <escribir_archivo> PRIMERO (para que siempre existan antes de ejecutar cualquier comando)
        for match in FILE_REGEX.finditer(cleaned_text):
            path = match.group(1) or match.group(2) or match.group(3)
            file_content = match.group(4)
            if file_content.startswith("\n"):
                file_content = file_content[1:]
            # Sanitizar si el modelo alucina tags o markdown dentro del archivo
            file_content = re.sub(r'</?(?:escribir_comando|ejecutar_comando|tool_call|escribir_archivo)[^>]*>', '', file_content, flags=re.IGNORECASE)
            file_content = re.sub(r'^```(?:python|bash|sh|json|text)?\s*\n', '', file_content, flags=re.IGNORECASE)
            file_content = re.sub(r'\n```\s*$', '', file_content)
            file_content = file_content.rstrip() + "\n"
            file_actions.append(
                ParsedAction(
                    action_type="file",
                    content=file_content,
                    target_path=path.strip(),
                )
            )

        # 2. Buscar comandos en etiquetas XML estándar <ejecutar_comando>
        for match in COMMAND_REGEX.finditer(cleaned_text):
            raw_cmd = match.group(1).strip()
            if not raw_cmd:
                continue

            # Si el contenido contiene otros bloques XML anidados o markdown sin cerrar, limpiar
            cmd = re.sub(r'<[^>]+>', '', raw_cmd).strip()
            # Si el comando empieza con ```bash o ```, limpiar los bloques de código
            cmd = re.sub(r'^```(?:bash|sh)?\s*', '', cmd, flags=re.MULTILINE)
            cmd = re.sub(r'\s*```$', '', cmd, flags=re.MULTILINE).strip()

            # Evitar falsos positivos como listas con guiones o texto explicativo
            if not cmd or cmd in seen_commands:
                continue
            
            # Si contiene líneas que claramente son explicaciones en texto (ej. "1. Identify Key Requirements:")
            # filtrar y quedarse solo con las líneas de comandos reales
            valid_lines = []
            for line in cmd.splitlines():
                l_strip = line.strip()
                if not l_strip:
                    continue
                # Si es un bullet point o texto conversacional en inglés/español
                if re.match(r'^(?:[•\-\*]|\d+\.|[A-Z][a-z]+ [a-z]+ [a-z]+|\b(?:Note|Step|Fase|Phase|Objective|Analyze|Structure|Draft|Use|This|Este|Ejecuta|Copia)\b)', l_strip, re.IGNORECASE):
                    continue
                # Si la línea tiene backticks sueltos (instrucciones de formato del modelo, no bash)
                if l_strip.count('`') >= 2 and not l_strip.startswith(('$', '#', '/', 'sudo', 'apt', 'pip', 'cd', 'cat', 'echo', 'curl', 'wget', 'nmap', 'dig', 'ffuf', 'whatweb', 'gobuster', 'openssl', 'python', 'bash', 'sh', 'grep', 'awk', 'sed', 'find', 'ls', 'chmod', 'chown', 'mkdir', 'cp', 'mv', 'rm', 'touch', 'head', 'tail', 'wc', 'sort', 'uniq', 'tee', 'xargs', 'export', 'source', 'set ')):
                    continue
                # Si la línea parece texto conversacional largo (más de 60 chars sin pipes/redirects/flags)
                if len(l_strip) > 60 and not re.search(r'[|><;&]|\s-[a-zA-Z]', l_strip):
                    continue
                valid_lines.append(line)

            final_cmd = "\n".join(valid_lines).strip()
            if not final_cmd or final_cmd in seen_commands:
                continue
            
            # Validación final: si el "comando" resultante contiene palabras que indican instrucciones del modelo, descartar
            if re.search(r'\b(for commands|if needed|Draft:|Operador|ejecutar_comando|escribir_archivo)\b', final_cmd, re.IGNORECASE):
                continue

            seen_commands.add(final_cmd)
            is_sudo = bool(re.search(r"\bsudo\b", final_cmd))
            is_dangerous = any(re.search(pat, final_cmd) for pat in CRITICAL_PATTERNS)
            cmd_actions.append(
                ParsedAction(
                    action_type="command",
                    content=final_cmd,
                    is_sudo=is_sudo,
                    is_dangerous=is_dangerous,
                )
            )

        # 3. Buscar comandos en formato JSON emitidos por modelos OSS / Groq
        json_cmd_regex = re.compile(r'\{[^{}]*"(?:cmd|command|bash|exec)"\s*:\s*(?:\[[^\]]*\]|"[^"]*")[^{}]*\}', re.DOTALL)
        for match in json_cmd_regex.finditer(cleaned_text):
            try:
                raw_json = match.group(0)
                data = json.loads(raw_json)
                cmd_val = data.get("cmd") or data.get("command") or data.get("exec") or data.get("bash")
                cmd_str = ""
                if isinstance(cmd_val, list):
                    if len(cmd_val) >= 3 and cmd_val[0] in ["bash", "sh", "/bin/bash", "/bin/sh"] and cmd_val[1] in ["-c", "-lc"]:
                        cmd_str = cmd_val[2]
                    else:
                        cmd_str = " ".join(cmd_val)
                elif isinstance(cmd_val, str):
                    cmd_str = cmd_val

                cmd_str = cmd_str.strip()
                if cmd_str and cmd_str not in seen_commands:
                    seen_commands.add(cmd_str)
                    is_sudo = bool(re.search(r"\bsudo\b", cmd_str))
                    is_dangerous = any(re.search(pat, cmd_str) for pat in CRITICAL_PATTERNS)
                    cmd_actions.append(
                        ParsedAction(
                            action_type="command",
                            content=cmd_str,
                            is_sudo=is_sudo,
                            is_dangerous=is_dangerous,
                        )
                    )
            except Exception:
                continue

        # SIEMPRE retornar primero la creación de archivos y luego los comandos
        return file_actions + cmd_actions

    def has_actions(self, text: str) -> bool:
        return bool(COMMAND_REGEX.search(text) or FILE_REGEX.search(text))

    def confirm_command(self, cmd: str, is_sudo: bool, is_dangerous: bool) -> bool:
        """Muestra panel visual y solicita confirmación al operador."""
        if is_dangerous:
            panel_title = "[bold red]⚠️  ¡ALERTA DE SEGURIDAD CRÍTICA! ⚠️[/bold red]"
            border_style = "bright_red"
        elif is_sudo:
            panel_title = "[bold yellow]⚡ COMANDO CON PRIVILEGIOS DE ROOT (SUDO) ⚡[/bold yellow]"
            border_style = "yellow"
        else:
            panel_title = "[bold cyan]🛠️  EJECUCIÓN DE COMANDO EN TERMINAL[/bold cyan]"
            border_style = "cyan"

        syntax = Syntax(cmd, "bash", theme="monokai", word_wrap=True, line_numbers=False)
        console.print()
        console.print(Panel(syntax, title=panel_title, border_style=border_style, padding=(1, 2)))

        if is_dangerous:
            console.print("[bold red][!] Advertencia: Este comando puede causar daños destructivos al sistema.[/bold red]")

        try:
            return Confirm.ask(
                "[bold green]¿Autorizar ejecución?[/bold green]",
                default=False,
                console=console
            )
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow][*] Operación cancelada por el usuario.[/yellow]")
            return False

    def confirm_file_write(self, path: str, content: str) -> bool:
        """Solicita confirmación antes de escribir o sobrescribir un archivo."""
        path_obj = Path(path).expanduser()
        exists = path_obj.exists()
        action_str = "SOBRESCRIBIR" if exists else "CREAR"
        border_style = "bright_magenta" if exists else "magenta"

        panel_title = f"[bold magenta]📝 {action_str} ARCHIVO: {path}[/bold magenta]"

        # Detectar lenguaje para resaltado de sintaxis
        ext = path_obj.suffix.lstrip(".") or "txt"
        preview_content = content if len(content) <= 2000 else content[:2000] + "\n\n... [Contenido truncado en la vista previa] ..."
        syntax = Syntax(preview_content, ext, theme="monokai", word_wrap=True, line_numbers=True)

        console.print()
        console.print(Panel(syntax, title=panel_title, border_style=border_style, padding=(1, 2)))

        if exists:
            console.print(f"[bold yellow][!] El archivo ya existe ({path_obj.stat().st_size} bytes). Será sobrescrito.[/bold yellow]")

        try:
            return Confirm.ask(
                f"[bold green]¿Autorizar {action_str.lower()} archivo en '{path}'?[/bold green]",
                default=False,
                console=console
            )
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow][*] Operación cancelada por el usuario.[/yellow]")
            return False

    def execute_command(self, cmd: str, is_sudo: bool = False, cwd: Optional[str] = None) -> ExecutionResult:
        """Ejecuta un comando en el sistema operativo capturando stdout y stderr."""
        console.print(f"[dim cyan][*] Ejecutando: {cmd}[/dim cyan]")

        # Si estamos en Linux y requiere sudo o interactividad
        if self.is_linux and is_sudo and not self.is_termux:
            return self._execute_linux_pty(cmd, cwd=cwd)
        else:
            return self._execute_standard(cmd, cwd=cwd)

    def _execute_linux_pty(self, cmd: str, cwd: Optional[str] = None) -> ExecutionResult:
        """Ejecuta en Linux usando PTY o pexpect para permitir interacción segura con sudo."""
        try:
            import pexpect

            # Ejecutar a través del shell dinámico resuelto
            child = pexpect.spawn(self.shell_path, ["-c", cmd], encoding="utf-8", timeout=600, cwd=cwd)
            output_chunks = []

            # Dejar que el usuario interactúe directamente si pide contraseña
            try:
                while True:
                    index = child.expect([r"\[sudo\] password for .*: ", pexpect.EOF, pexpect.TIMEOUT], timeout=3)
                    if index == 0:
                        # Reenviar prompt a la terminal real
                        sys.stdout.write(child.after)
                        sys.stdout.flush()
                        import getpass
                        pwd = getpass.getpass("")
                        child.sendline(pwd)
                    elif index == 1:
                        output_chunks.append(child.before)
                        break
                    elif index == 2:
                        # Timeout parcial, guardar chunk y continuar
                        output_chunks.append(child.before)
            except pexpect.EOF:
                output_chunks.append(child.before)
            except Exception as e:
                output_chunks.append(f"\n[!] Excepción en PTY: {e}\n")

            child.close()
            full_output = "".join(output_chunks).strip()
            if not full_output:
                full_output = "[Comando ejecutado sin salida estándar]"
            elif len(full_output) > 20000:
                full_output = full_output[:10000] + "\n\n... [Salida extensa truncada] ...\n\n" + full_output[-5000:]

            return ExecutionResult(
                success=(child.exitstatus == 0),
                output=full_output,
                returncode=child.exitstatus or 0,
                command=cmd,
            )
        except ImportError:
            # Si pexpect no está disponible, usar subprocess normal
            return self._execute_standard(cmd, cwd=cwd)
        except Exception as e:
            return ExecutionResult(
                success=False,
                output=f"Error durante la ejecución en PTY: {str(e)}",
                returncode=1,
                command=cmd,
            )

    def _execute_standard(self, cmd: str, cwd: Optional[str] = None) -> ExecutionResult:
        """Ejecución estándar mediante subprocess (PowerShell en Windows, Bash/Sh en Linux y Termux)."""
        try:
            if self.is_linux:
                shell_cmd = [self.shell_path, "-c", cmd]
                use_shell = False
            elif self.is_windows:
                # En Windows ejecutar a través de PowerShell para soportar scripts, netsh, Get-NetAdapter, etc.
                shell_cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd]
                use_shell = False
            else:
                shell_cmd = cmd
                use_shell = True

            # Soporte nativo para ejecución en segundo plano (background tasks)
            is_background = cmd.strip().endswith("&") or "nohup " in cmd or "Start-Process" in cmd or "run_background" in cmd
            
            if is_background and self.is_linux:
                # Asegurar ejecución limpia en background en Linux/Termux redirigiendo logs a tempfile
                tmp_dir = tempfile.gettempdir()
                log_file = os.path.join(tmp_dir, "blood_cipher_task.log")
                bg_cmd = cmd.strip()
                if not bg_cmd.endswith("&"):
                    bg_cmd += f" > {log_file} 2>&1 &"
                clean_cmd = f"nohup {bg_cmd}"
                process = subprocess.Popen(
                    [self.shell_path, "-c", clean_cmd],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    close_fds=True,
                    cwd=cwd,
                )
                pid_info = process.pid
                return ExecutionResult(
                    success=True,
                    output=f"[⚡ SEGUNDO PLANO ACTIVO] Tarea iniciada en background (PID {pid_info}). Los registros se escriben en '{log_file}'. Puedes seguir conversando con Blood-Cipher libremente mientras el script procesa los datos.",
                    returncode=0,
                    command=cmd,
                )

            process = subprocess.Popen(
                shell_cmd,
                shell=use_shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=cwd,
            )
            stdout, stderr = process.communicate(timeout=600)
            combined_output = []
            if stdout:
                combined_output.append(stdout.strip())
            if stderr:
                combined_output.append(f"[STDERR]\n{stderr.strip()}")

            final_output = "\n".join(combined_output).strip()
            if not final_output:
                final_output = "[Comando ejecutado con éxito (código de salida 0), sin salida estándar]"

            # Truncar salidas gigantes (ej. bundles JS minificados)
            max_chars = 20000
            if len(final_output) > max_chars:
                total_len = len(final_output)
                final_output = (
                    final_output[:10000]
                    + f"\n\n... [Salida muy extensa: {total_len} caracteres detectados. Truncado para preservar contexto de IA] ...\n\n"
                    + final_output[-5000:]
                )

            return ExecutionResult(
                success=process.returncode == 0,
                output=final_output,
                returncode=process.returncode,
                command=cmd,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                output="[!] Tiempo de espera agotado (Timeout de 600 segundos excedido).",
                returncode=124,
                command=cmd,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output=f"Error al ejecutar comando: {str(e)}",
                returncode=1,
                command=cmd,
            )

    def write_file(self, target_path: str, content: str, cwd: Optional[str] = None) -> ExecutionResult:
        """Crea o sobrescribe un archivo en el sistema de archivos."""
        try:
            p = Path(target_path).expanduser()
            if not p.is_absolute() and cwd:
                path_obj = (Path(cwd) / p).resolve()
            else:
                path_obj = p.resolve()
            # Crear directorios padres si no existen
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            path_obj.write_text(content, encoding="utf-8")

            msg = f"[✓] Archivo '{path_obj}' escrito exitosamente ({len(content.encode('utf-8'))} bytes)."
            return ExecutionResult(
                success=True,
                output=msg,
                returncode=0,
                target_path=str(path_obj),
                is_file_op=True,
            )
        except Exception as e:
            err_msg = f"[!] Error al escribir en '{target_path}': {str(e)}"
            return ExecutionResult(
                success=False,
                output=err_msg,
                returncode=1,
                target_path=target_path,
                is_file_op=True,
            )

    def process_action(self, action: ParsedAction, cwd: Optional[str] = None) -> ExecutionResult:
        """Procesa una acción individual (comando o archivo) gestionando la confirmación y cwd."""
        if action.action_type == "command":
            # Comandos normales (no sudo y no críticos) se ejecutan automáticamente sin interrumpir
            requires_confirmation = action.is_sudo or action.is_dangerous
            if not requires_confirmation:
                authorized = True
            else:
                authorized = self.confirm_command(
                    action.content,
                    is_sudo=action.is_sudo,
                    is_dangerous=action.is_dangerous,
                )
            if not authorized:
                return ExecutionResult(
                    success=False,
                    output="[RECHAZADO] El operador canceló la ejecución del comando de superusuario.",
                    returncode=130,
                    command=action.content,
                    was_rejected=True,
                )
            return self.execute_command(action.content, is_sudo=action.is_sudo, cwd=cwd)

        elif action.action_type == "file":
            if not action.target_path:
                return ExecutionResult(
                    success=False,
                    output="[ERROR] No se especificó la ruta de archivo en la etiqueta XML.",
                    returncode=1,
                    is_file_op=True,
                )
            if self.auto_approve_safe and not action.is_dangerous:
                authorized = True
            else:
                authorized = self.confirm_file_write(action.target_path, action.content)
            if not authorized:
                return ExecutionResult(
                    success=False,
                    output=f"[RECHAZADO] El operador canceló la creación del archivo '{action.target_path}'.",
                    returncode=130,
                    target_path=action.target_path,
                    was_rejected=True,
                    is_file_op=True,
                )
            return self.write_file(action.target_path, action.content)

        return ExecutionResult(
            success=False,
            output="[ERROR] Tipo de acción desconocido.",
            returncode=1,
        )
