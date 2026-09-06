"""
coder_kali/cli.py - Enrutador Principal de Comandos CLI con Typer.
Punto de entrada de la aplicación para chat interactivo, configuración, ejecución directa y diagnóstico.
"""

import os
import sys
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
import typer
from rich.console import Console
from rich.prompt import Prompt

from coder_kali import __version__
from coder_kali.config import ConfigManager
from coder_kali.agent import KaliAgent
from coder_kali.session_manager import SessionManager, ChatSession
from coder_kali.scope_manager import ScopeManager
from coder_kali.system_executor import SystemExecutor
from coder_kali.tools_database import KaliToolsDatabase
from coder_kali.ui.chat_render import (
    print_banner,
    render_user_message,
    render_error,
    render_info,
    render_system_status,
    render_ai_message,
)
from coder_kali.ui.config_menus import interactive_config_wizard, test_provider_connection

# Asegurar codificación UTF-8 en terminales Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

app = typer.Typer(
    name="blood-cipher",
    help="Blood-Cipher - Agente de IA para Hacktivismo, OSINT y Auditorias en Linux.",
    add_completion=False,
)
console = Console()


def prompt_session_selection(session_mgr: SessionManager) -> Optional[str]:
    """Muestra un menú interactivo para continuar un chat anterior o crear uno nuevo."""
    import questionary
    sessions = session_mgr.list_sessions()
    if not sessions:
        return None

    choices = [
        questionary.Choice(
            title="➕ [Iniciar Nueva Sesión Limpia]",
            value="NEW"
        )
    ]

    import time
    for s in sessions[:15]:
        time_str = time.strftime('%d/%m %H:%M', time.localtime(s.updated_at))
        msg_count = len([m for m in s.messages if m.get("role") == "user"])
        choices.append(
            questionary.Choice(
                title=f"💬 {s.title}  [dim]({time_str} • {msg_count} msgs • {s.provider})[/dim]",
                value=s.id
            )
        )

    chosen = questionary.select(
        "¿Deseas reanudar una sesión anterior o comenzar una nueva?",
        choices=choices,
        default=choices[0],
    ).ask()

    if chosen == "NEW" or not chosen:
        return None
    return chosen


def interactive_scope_menu(scope_mgr: ScopeManager):
    """Menú interactivo para gestionar documentos de alcance (SOW) y autorizaciones de seguridad."""
    import questionary
    from rich.panel import Panel
    from rich.markdown import Markdown

    while True:
        active = scope_mgr.get_active_scope_name()
        active_str = f"[bold green]{active}[/bold green]" if active else "[dim]Ninguno (Modo Libre)[/dim]"
        console.print(f"\n[bold cyan]🎯 Gestor de Alcance y Autorización (SOW / ROE)[/bold cyan] | Activo: {active_str}")

        action = questionary.select(
            "¿Qué acción deseas realizar con los documentos de alcance?",
            choices=[
                questionary.Choice("👁️  Ver contenido del Scope activo", value="VIEW"),
                questionary.Choice("🔄 Cambiar / Activar un Scope existente", value="SELECT"),
                questionary.Choice("✏️  Editar un Scope existente", value="EDIT"),
                questionary.Choice("📥 Importar Scope desde un archivo (.md / .txt)", value="IMPORT"),
                questionary.Choice("✍️  Crear / Pegar nuevo Scope manualmente", value="CREATE"),
                questionary.Choice("❌ Desactivar Scope actual (Modo Libre)", value="CLEAR"),
                questionary.Choice("🗑️  Eliminar un documento de Scope", value="DELETE"),
                questionary.Choice("🔙 Volver al chat", value="BACK"),
            ]
        ).ask()

        if not action or action == "BACK":
            break

        if action == "VIEW":
            content = scope_mgr.get_active_scope_content()
            if content:
                console.print(Panel(Markdown(content), title=f"[bold green]🎯 Alcance Activo: {active}[/bold green]", border_style="green"))
            else:
                console.print("[yellow][!] No hay ningún documento de alcance activo actualmente.[/yellow]")

        elif action == "SELECT":
            scopes = scope_mgr.list_scopes()
            if not scopes:
                console.print("[yellow][i] No hay documentos de alcance guardados aún.[/yellow]")
                continue
            choices = [questionary.Choice(f"📄 {s['name']}  [dim]({s['preview']})[/dim]", value=s["name"]) for s in scopes]
            chosen_scope = questionary.select("Elige el alcance a activar:", choices=choices).ask()
            if chosen_scope:
                scope_mgr.set_active_scope(chosen_scope)
                console.print(f"[bold green][✓] Alcance activado:[/bold green] [bold white]{chosen_scope}[/bold white]")

        elif action == "EDIT":
            scopes = scope_mgr.list_scopes()
            if not scopes:
                console.print("[yellow][i] No hay documentos de alcance para editar.[/yellow]")
                continue
            choices = [questionary.Choice(f"📄 {s['name']}  [dim]({s['preview']})[/dim]", value=s["name"]) for s in scopes]
            chosen_scope = questionary.select("Elige el alcance a editar:", choices=choices).ask()
            if chosen_scope:
                edit_mode = questionary.select(
                    f"¿Cómo deseas editar '{chosen_scope}'?",
                    choices=[
                        questionary.Choice("📝 Abrir en editor de texto del sistema ($EDITOR / nano / vim / notepad)", value="EDITOR"),
                        questionary.Choice("✍️  Pegar o escribir nuevo contenido directamente aquí", value="PASTE"),
                        questionary.Choice("🔙 Cancelar", value="CANCEL"),
                    ]
                ).ask()

                if edit_mode == "EDITOR":
                    target_file = scope_mgr.get_scope_path(chosen_scope)
                    editor = os.environ.get("EDITOR") or ("nano" if shutil.which("nano") else ("vim" if shutil.which("vim") else ("notepad" if os.name == "nt" else "vi")))
                    try:
                        import subprocess
                        subprocess.run([editor, str(target_file)])
                        console.print(f"[bold green][✓] Scope '{chosen_scope}' guardado exitosamente desde {editor}.[/bold green]")
                    except Exception as e:
                        console.print(f"[bold red][!] Error al abrir el editor {editor}: {e}[/bold red]")

                elif edit_mode == "PASTE":
                    console.print(f"[cyan][*] Ingresa el nuevo contenido para '{chosen_scope}' (escribe 'FIN' en una línea vacía para guardar):[/cyan]")
                    lines = []
                    while True:
                        try:
                            line = input()
                            if line.strip() == "FIN":
                                break
                            lines.append(line)
                        except (KeyboardInterrupt, EOFError):
                            break
                    new_content = "\n".join(lines)
                    if new_content.strip():
                        scope_mgr.save_scope(chosen_scope, new_content)
                        console.print(f"[bold green][✓] Scope '{chosen_scope}' actualizado exitosamente.[/bold green]")

        elif action == "IMPORT":
            file_path_str = questionary.text("Ingresa la ruta absoluta o relativa al archivo (.md o .txt):").ask()
            if file_path_str:
                p = Path(file_path_str.strip()).expanduser()
                if p.exists() and p.is_file():
                    try:
                        content = p.read_text(encoding="utf-8")
                        name = p.stem
                        saved_name = scope_mgr.save_scope(name, content)
                        scope_mgr.set_active_scope(saved_name)
                        console.print(f"[bold green][✓] Scope '{saved_name}' importado y activado exitosamente.[/bold green]")
                    except Exception as e:
                        console.print(f"[bold red][!] Error al leer el archivo: {e}[/bold red]")
                else:
                    console.print(f"[bold red][!] El archivo '{file_path_str}' no existe.[/bold red]")

        elif action == "CREATE":
            name = questionary.text("Nombre del objetivo o proyecto (ej. binsperu_audit):").ask()
            if name:
                console.print("[cyan][*] Ingresa el texto o documento SOW (finaliza escribiendo 'FIN' en una línea vacía):[/cyan]")
                lines = []
                while True:
                    try:
                        line = input()
                        if line.strip() == "FIN":
                            break
                        lines.append(line)
                    except (KeyboardInterrupt, EOFError):
                        break
                content = "\n".join(lines)
                if content.strip():
                    saved = scope_mgr.save_scope(name, content)
                    scope_mgr.set_active_scope(saved)
                    console.print(f"[bold green][✓] Scope '{saved}' guardado y activado.[/bold green]")

        elif action == "CLEAR":
            scope_mgr.clear_active_scope()
            console.print("[bold yellow][✓] Alcance desactivado. Blood-Cipher vuelve a operar en modo libre.[/bold yellow]")

        elif action == "DELETE":
            scopes = scope_mgr.list_scopes()
            if not scopes:
                console.print("[yellow]No hay scopes para eliminar.[/yellow]")
                continue
            choices = [questionary.Choice(s["name"], value=s["name"]) for s in scopes]
            to_del = questionary.select("Elige el scope a eliminar:", choices=choices).ask()
            if to_del:
                scope_mgr.delete_scope(to_del)
                console.print(f"[bold green][✓] Scope '{to_del}' eliminado.[/bold green]")


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Muestra la versión de Blood-Cipher."),
    new_session: bool = typer.Option(False, "--new", "-n", help="Inicia una nueva sesión sin preguntar por el historial."),
):
    """Comando por defecto cuando se invoca blood-cipher sin argumentos."""
    if version:
        console.print(f"[bold cyan]blood-cipher[/bold cyan] versión [bold green]{__version__}[/bold green]")
        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        chat(new_session=new_session)


def _get_windows_clipboard_text() -> Optional[str]:
    """Obtiene el texto actual del portapapeles de Windows de forma directa mediante la API Win32."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        if not user32.OpenClipboard(None):
            return None
        try:
            CF_UNICODETEXT = 13
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return None
            kernel32.GlobalLock.restype = ctypes.c_wchar_p
            ptr = kernel32.GlobalLock(handle)
            text = str(ptr) if ptr else None
            kernel32.GlobalUnlock(handle)
            return text
        finally:
            user32.CloseClipboard()
    except Exception:
        return None


def _get_multiline_user_input() -> str:
    """
    Captura la entrada del usuario soportando pegado de textos largos multilínea en Windows y Linux.
    Permite pegar con Ctrl+V, Shift+Insert, clic derecho o drenado directo del buffer.
    """
    import platform
    is_windows = platform.system() == "Windows"
    prompt_str = "\x1b[1;96mblood-cipher >\x1b[0m " if is_windows else "\x1b[1;92mblood-cipher >\x1b[0m "
    rich_prompt = "[bold bright_cyan]blood-cipher >[/bold bright_cyan]" if is_windows else "[bold bright_green]blood-cipher >[/bold bright_green]"

    # 1. Intentar con prompt_toolkit vinculando Ctrl+V al portapapeles nativo
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.formatted_text import ANSI
        from prompt_toolkit.key_binding import KeyBindings

        kb = KeyBindings()

        if is_windows:
            @kb.add("c-v")
            def _handle_paste_ctrl_v(event):
                """Mapeo explícito de Ctrl+V al portapapeles del sistema Windows."""
                clip_text = _get_windows_clipboard_text()
                if clip_text:
                    event.current_buffer.insert_text(clip_text)

        session = PromptSession(key_bindings=kb)
        user_text = session.prompt(
            ANSI(prompt_str),
            multiline=False,
        )
        return user_text.strip() if user_text else ""
    except Exception:
        pass

    # 2. Fallback a lectura estándar
    first_line = Prompt.ask(rich_prompt)
    if not first_line:
        return ""

    lines = [first_line]

    if is_windows:
        try:
            import msvcrt
            import time
            time.sleep(0.05)
            extra_chars = []
            while msvcrt.kbhit():
                ch = msvcrt.getwche() if hasattr(msvcrt, "getwche") else msvcrt.getch().decode("utf-8", errors="ignore")
                extra_chars.append(ch)
            if extra_chars:
                for l in "".join(extra_chars).splitlines():
                    if l:
                        lines.append(l)
        except Exception:
            pass
    else:
        import select
        while True:
            rlist, _, _ = select.select([sys.stdin], [], [], 0.05)
            if rlist:
                line = sys.stdin.readline()
                if not line:
                    break
                lines.append(line.rstrip("\r\n"))
            else:
                break

    return "\n".join(lines).strip()


@app.command(name="chat", help="Inicia una sesión de chat interactiva en vivo con Blood-Cipher.")
def chat(
    new_session: bool = typer.Option(False, "--new", "-n", help="Inicia una nueva sesión sin preguntar por el historial.")
):
    """Modo conversacional interactivo con terminal enriquecida."""
    config_mgr = ConfigManager()
    session_mgr = SessionManager()
    scope_mgr = ScopeManager()

    # Si no está configurado, ofrecer wizard inicial
    if not config_mgr.is_configured():
        console.print("[yellow][!] Blood-Cipher no tiene un proveedor de IA o API Key configurada.[/yellow]")
        console.print("[cyan][*] Iniciando asistente de configuración inicial...[/cyan]")
        configured = interactive_config_wizard(config_mgr)
        if not configured:
            console.print("[red][!] No se completó la configuración. Saliendo...[/red]")
            raise typer.Exit(1)

    selected_session_id = None
    if not new_session:
        selected_session_id = prompt_session_selection(session_mgr)

    agent = KaliAgent(config_mgr=config_mgr, session_mgr=session_mgr, scope_mgr=scope_mgr, session_id=selected_session_id)

    provider = config_mgr.get_active_provider()
    model = config_mgr.get_active_model()
    active_scope_name = scope_mgr.get_active_scope_name()
    key_pool_size = config_mgr.get_api_key_count(provider)
    workspace_path = getattr(agent.current_session, "workspace_path", None)
    print_banner(version=__version__, provider=provider, model=model, scope=active_scope_name, key_pool_size=key_pool_size, workspace=workspace_path)

    if selected_session_id and agent.current_session:
        user_msgs = [m for m in agent.messages if m.get("role") == "user" and not m.get("content", "").startswith("[RESULTADOS_SISTEMA")]
        console.print(f"[bold green][✓] Sesión reanudada:[/bold green] [bold white]'{agent.current_session.title}'[/bold white] [dim]({len(user_msgs)} turnos en memoria táctica)[/dim]\n")
        
        # Renderizar los últimos mensajes visibles para contexto visual inmediato
        _internal_prefixes = ("[RESULTADOS_SISTEMA", "Interpreta los resultados", "Interpreta ahora", "Analiza estos resultados", "Presenta tu resumen")
        visible_msgs = [
            m for m in agent.messages 
            if m.get("role") in ["user", "assistant"] 
            and not any(m.get("content", "").startswith(p) for p in _internal_prefixes)
        ][-4:]
        for msg in visible_msgs:
            if msg.get("role") == "user":
                render_user_message(msg.get("content", "").split("\n\n[REFERENCIA")[0])
            elif msg.get("role") == "assistant":
                render_ai_message(msg.get("content", ""))

    while True:
        try:
            user_input = _get_multiline_user_input()
            if not user_input or not user_input.strip():
                continue

            cleaned_cmd = user_input.strip().lower()

            # Comandos de navegación y control interactivo
            if cleaned_cmd in ["inicio", "home", "menu", "principal", "banner"]:
                os.system("clear" if os.name != "nt" else "cls")
                provider = config_mgr.get_active_provider()
                model = config_mgr.get_active_model()
                active_scope_name = scope_mgr.get_active_scope_name()
                key_pool_size = config_mgr.get_api_key_count(provider)
                workspace_path = getattr(agent.current_session, "workspace_path", None)
                print_banner(version=__version__, provider=provider, model=model, scope=active_scope_name, key_pool_size=key_pool_size, workspace=workspace_path)
                continue
            elif cleaned_cmd in ["exit", "quit", "salir", "q"]:
                console.print("[bold cyan]Hasta pronto, operador. Tu sesión quedó guardada en el historial.[/bold cyan]")
                break
            elif cleaned_cmd in ["clear", "cls", "limpiar"]:
                os.system("clear" if os.name != "nt" else "cls")
                active_scope_name = scope_mgr.get_active_scope_name()
                workspace_path = getattr(agent.current_session, "workspace_path", None)
                print_banner(version=__version__, provider=provider, model=model, scope=active_scope_name, workspace=workspace_path)
                continue
            elif cleaned_cmd in ["new", "nuevo", "reset", "reiniciar"]:
                agent = KaliAgent(config_mgr=config_mgr, session_mgr=session_mgr, scope_mgr=scope_mgr)
                workspace_path = getattr(agent.current_session, "workspace_path", None)
                console.print(f"[bold green][✓] Nueva sesión iniciada:[/bold green] [dim]{workspace_path}[/dim]")
                continue
            elif cleaned_cmd in ["historial", "history", "sesiones"]:
                sid = prompt_session_selection(session_mgr)
                if sid:
                    agent = KaliAgent(config_mgr=config_mgr, session_mgr=session_mgr, scope_mgr=scope_mgr, session_id=sid)
                    console.print(f"[bold green][✓] Sesión '{agent.current_session.title}' cargada exitosamente.[/bold green]")
                continue
            elif cleaned_cmd in ["scope", "alcance", "sow", "roe"]:
                interactive_scope_menu(scope_mgr)
                active_scope_name = scope_mgr.get_active_scope_name()
                if active_scope_name:
                    console.print(f"[bold green][✓] Alcance activo actualizado a:[/bold green] [bold white]{active_scope_name}[/bold white]")
                continue
            elif cleaned_cmd in ["config", "configurar", "modelo", "model", "provider"]:
                changed = interactive_config_wizard(config_mgr)
                if changed:
                    provider = config_mgr.get_active_provider()
                    model = config_mgr.get_active_model()
                    agent = KaliAgent(config_mgr=config_mgr, session_mgr=session_mgr, scope_mgr=scope_mgr, session_id=agent.current_session.id)
                continue
            elif cleaned_cmd in ["creds", "credenciales", "hashes"]:
                _interactive_creds_menu()
                continue
            elif cleaned_cmd in ["vpn", "opsec", "anon", "ip", "red", "network"]:
                from coder_kali.ui.vpn_menu import interactive_vpn_menu
                interactive_vpn_menu()
                continue
            elif cleaned_cmd in ["vulns", "vulnerabilidades", "scan"]:
                console.print("[bold cyan][*] Usa 'blood-cipher audit vulns <target>' desde la terminal o escribe tu solicitud de auditoría aquí.[/bold cyan]")
                continue
            elif cleaned_cmd in ["ayuda", "help", "?"]:
                console.print("""
[bold cyan]🎮 Comandos Rápidos e Interactivos del Chat:[/bold cyan]
  [bold green]inicio / menu[/bold green]   - Redibujar la interfaz y el banner táctico principal
  [bold green]vpn / ip / anon[/bold green] - Gestor táctico Multi-VPN, comprobación de IP y OPSEC
  [bold green]scope / sow[/bold green]     - Cambiar, crear o importar un nuevo objetivo/alcance (SOW)
  [bold green]config / model[/bold green]  - Cambiar de modelo de IA o API Key al vuelo sin reiniciar
  [bold green]historial[/bold green]       - Listar y cambiar entre sesiones de chat anteriores
  [bold green]new / nuevo[/bold green]     - Iniciar un nuevo chat limpio
  [bold green]clear[/bold green]           - Limpiar la pantalla de la terminal
  [bold green]exit / salir[/bold green]    - Guardar y salir de Blood-Cipher
  [bold cyan]Ctrl + C[/bold cyan]        - Cancelar acción actual / Regresar al menú anterior
                """)
                continue

            # Renderizar mensaje del usuario
            render_user_message(user_input)

            # Ejecutar turno de razonamiento y acción
            agent.send_message(user_input)

        except KeyboardInterrupt:
            # Captura de Ctrl+C suave: volver al prompt sin matar la aplicación bruscamente
            console.print("\n[yellow][*] Operación interrumpida (Ctrl+C). Escribe 'inicio' para ver el panel o 'exit' para salir.[/yellow]")
            continue
        except EOFError:
            console.print("\n[bold cyan]Sesión guardada. Cerrando Blood-Cipher...[/bold cyan]")
            break
        except Exception as e:
            render_error("Excepción en la sesión", str(e))


@app.command(name="config", help="Abre el menú interactivo para configurar proveedores y API Keys.")
def config():
    """Configura modelos, API keys y opciones del sistema."""
    config_mgr = ConfigManager()
    interactive_config_wizard(config_mgr)


@app.command(name="history", help="📜 Lista y administra todas las sesiones y chats guardados.")
def history(
    clear: bool = typer.Option(False, "--clear", "-c", help="Eliminar todo el historial de sesiones guardadas.")
):
    """Muestra la lista de conversaciones guardadas con su título y fecha."""
    from rich.table import Table
    session_mgr = SessionManager()

    if clear:
        confirm = typer.confirm("¿Estás seguro de eliminar todo el historial de chats?")
        if confirm:
            for s in session_mgr.list_sessions():
                session_mgr.delete_session(s.id)
            console.print("[bold green][✓] Historial de chats eliminado.[/bold green]")
        return

    sessions = session_mgr.list_sessions()
    if not sessions:
        console.print("[yellow][i] No hay sesiones guardadas en el historial todavía.[/yellow]")
        return

    import time
    table = Table(title="Historial de Sesiones Blood-Cipher", border_style="cyan")
    table.add_column("ID", style="bold green", width=10)
    table.add_column("Título / Primera Petición", style="bold white")
    table.add_column("Proveedor / Modelo", style="cyan")
    table.add_column("Mensajes", style="yellow")
    table.add_column("Última Actividad", style="dim")

    for s in sessions:
        time_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(s.updated_at))
        msg_count = len([m for m in s.messages if m.get("role") == "user"])
        table.add_row(
            s.id,
            s.title,
            f"{s.provider} ({s.model.split('/')[-1]})",
            str(msg_count),
            time_str
        )

    console.print(table)
    console.print("\n[dim]Para reanudar un chat específico ejecuta: blood-cipher (y selecciónalo del menú interactivo)[/dim]")


@app.command(name="scope", help="🎯 Administra documentos de alcance de trabajo (SOW / ROE) y autorizaciones.")
def scope_command(
    set_scope: Optional[str] = typer.Option(None, "--set", "-s", help="Activar un scope por nombre."),
    clear: bool = typer.Option(False, "--clear", "-c", help="Desactivar el scope activo (volver a modo libre)."),
    show: bool = typer.Option(False, "--show", help="Muestra el contenido del scope activo."),
    import_file: Optional[str] = typer.Option(None, "--import", "-i", help="Importar un archivo de alcance (.md o .txt)."),
):
    """Gestor de alcance y documentos de autorización de seguridad."""
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.table import Table

    scope_mgr = ScopeManager()

    if clear:
        scope_mgr.clear_active_scope()
        console.print("[bold yellow][✓] Alcance desactivado. Blood-Cipher vuelve a operar en modo libre.[/bold yellow]")
        return

    if set_scope:
        if scope_mgr.set_active_scope(set_scope):
            console.print(f"[bold green][✓] Alcance activado:[/bold green] [bold white]{set_scope}[/bold white]")
        else:
            console.print(f"[bold red][!] No existe ningún scope con el nombre '{set_scope}'.[/bold red]")
        return

    if import_file:
        p = Path(import_file).expanduser()
        if p.exists() and p.is_file():
            content = p.read_text(encoding="utf-8")
            saved = scope_mgr.save_scope(p.stem, content)
            scope_mgr.set_active_scope(saved)
            console.print(f"[bold green][✓] Scope '{saved}' importado y activado exitosamente.[/bold green]")
        else:
            console.print(f"[bold red][!] El archivo '{import_file}' no existe.[/bold red]")
        return

    if show:
        content = scope_mgr.get_active_scope_content()
        name = scope_mgr.get_active_scope_name()
        if content:
            console.print(Panel(Markdown(content), title=f"[bold green]🎯 Alcance Activo: {name}[/bold green]", border_style="green"))
        else:
            console.print("[yellow][!] No hay ningún alcance activo actualmente.[/yellow]")
        return

    # Si no se pasó ningún flag, abrir el menú interactivo
    interactive_scope_menu(scope_mgr)


@app.command(name="web", help="Inicia el Centro de Operaciones Visual / Dashboard Web en el navegador.")
def web_dashboard(
    port: int = typer.Option(7777, "--port", "-p", help="Puerto HTTP para el servidor web local."),
    no_open: bool = typer.Option(False, "--no-open", help="No abrir automáticamente el navegador."),
):
    """Lanza la interfaz web táctica de Blood-Cipher en el navegador."""
    from coder_kali.web_server import start_web_server
    config_mgr = ConfigManager()
    if not config_mgr.is_configured():
        console.print("[yellow][!] Se recomienda configurar una API Key primero con 'blood-cipher config'.[/yellow]")

    start_web_server(port=port, open_browser=not no_open)


@app.command(name="ui", help="Alias para 'blood-cipher web' (Panel Gráfico Web).")
def ui_dashboard(
    port: int = typer.Option(7777, "--port", "-p", help="Puerto HTTP para el servidor web local."),
    no_open: bool = typer.Option(False, "--no-open", help="No abrir automáticamente el navegador."),
):
    """Alias de blood-cipher web."""
    web_dashboard(port=port, no_open=no_open)


@app.command(name="run", help="Ejecuta una instrucción directa en una sola línea sin entrar al chat.")
def run_command_line(
    prompt: str = typer.Argument(..., help="Instrucción o tarea a ejecutar (ej. 'audita puertos locales')")
):
    """Ejecución de un solo disparo desde la terminal."""
    config_mgr = ConfigManager()
    if not config_mgr.is_configured():
        console.print("[yellow][!] Configura primero Blood-Cipher ejecutando 'blood-cipher config'.[/yellow]")
        raise typer.Exit(1)

    agent = KaliAgent(config_mgr=config_mgr)
    render_user_message(prompt)
    agent.send_message(prompt)


@app.command(name="exclude-antivirus", help="🛡️ Agrega la carpeta de Blood-Cipher a las exclusiones de Windows Defender en tiempo real.")
def exclude_antivirus():
    """Agrega automáticamente la carpeta actual a las exclusiones de Windows Defender."""
    import platform
    if platform.system() != "Windows":
        console.print("[yellow][!] Este comando está diseñado para sistemas Microsoft Windows.[/yellow]")
        return

    current_path = Path.cwd().resolve()
    temp_path = Path(os.environ.get("TEMP", "C:\\Temp")).resolve()

    console.print(Panel(
        f"[bold cyan]Añadiendo exclusión de Antivirus en tiempo real para:[/bold cyan]\n"
        f"📁 [bold white]{current_path}[/bold white]\n"
        f"📁 [bold white]{temp_path}[/bold white]",
        title="🛡️ EXCLUSIÓN DE ANTIVIRUS (WINDOWS DEFENDER)",
        border_style="cyan"
    ))

    cmd = (
        f'powershell -Command "Start-Process powershell -Verb RunAs -ArgumentList '
        f'\'Add-MpPreference -ExclusionPath \"\"\"{current_path}\"\"\",\"\"\"{temp_path}\"\"\" -Force\'"'
    )
    try:
        subprocess.run(cmd, shell=True, check=True)
        console.print("[bold green][✓] Solicitud de elevación enviada a Windows Defender.[/bold green]")
        console.print("[dim]Si aceptaste el aviso de Administrador (UAC), la carpeta ya no será bloqueada ni escaneada por el antivirus.[/dim]")
    except Exception as e:
        console.print(f"[bold red][!] Error al configurar exclusión: {e}[/bold red]")


@app.command(name="doctor", help="Comprueba el estado del sistema, dependencias y herramientas de seguridad.")
def doctor():
    """Diagnóstico del entorno y herramientas."""
    import platform

    config_mgr = ConfigManager()
    os_name = platform.system()
    py_ver = sys.version.split()[0]

    # Verificar herramientas comunes de Kali / Pentesting / Arch
    tools = [
        "nmap",
        "nikto",
        "gobuster",
        "hydra",
        "sqlmap",
        "wireshark",
        "tshark",
        "msfconsole",
        "john",
        "aircrack-ng",
        "ffuf",
        "curl",
        "docker",
        "git",
        "pacman",
        "yay",
        "paru",
        "apt",
    ]

    tools_status = {}
    for tool in tools:
        path = shutil.which(tool)
        tools_status[tool] = "[green]Instalado[/green]" if path else "[dim red]No encontrado[/dim red]"

    status_data = {
        "Sistema Operativo": f"{os_name} ({platform.release()})",
        "Versión de Python": py_ver,
        "Proveedor Activo": config_mgr.get_active_provider(),
        "Modelo Activo": config_mgr.get_active_model(),
        "API Key Configurada": "[green]Sí[/green]" if config_mgr.is_configured() else "[red]No[/red]",
        "Herramientas Detectadas": ", ".join([t for t, s in tools_status.items() if "Instalado" in s]) or "Ninguna específica",
    }

    render_system_status(status_data)


# ==============================================================================
# SUBCOMANDOS DE HERRAMIENTAS Y SCRAPING (https://www.kali.org/tools/)
# ==============================================================================
tools_app = typer.Typer(
    name="tools",
    help="🧰 Base de conocimiento y scraper oficial de herramientas de Kali Linux (https://www.kali.org/tools/).",
)
app.add_typer(tools_app, name="tools")


@tools_app.command(name="list", help="Lista las herramientas y categorías disponibles en la base de datos local.")
def list_tools():
    """Muestra todas las herramientas indexadas por categoría."""
    from rich.table import Table
    from coder_kali.tools_database import KaliToolsDatabase

    db = KaliToolsDatabase()
    categories = db.get_categories()

    table = Table(title="🧰 Herramientas de Kali Linux Indexadas", box=typer.colors.RESET)
    table.add_column("Categoría", style="bold cyan")
    table.add_column("Herramientas", style="white")

    total = 0
    for cat, tools in categories.items():
        table.add_row(cat, ", ".join(tools))
        total += len(tools)

    console.print(table)
    console.print(f"\n[bold green]Total de herramientas indexadas:[/bold green] {total}")


@tools_app.command(name="search", help="Busca una herramienta por nombre, comando o palabra clave.")
def search_tools(
    query: str = typer.Argument(..., help="Término de búsqueda (ej. 'fuzzing', 'wifi', 'sql', 'nmap')")
):
    """Busca herramientas en la base de conocimiento."""
    from rich.table import Table
    from coder_kali.tools_database import KaliToolsDatabase

    db = KaliToolsDatabase()
    results = db.search_tools(query)

    if not results:
        console.print(f"[yellow][!] No se encontraron herramientas para: '{query}'[/yellow]")
        return

    table = Table(title=f"Resultados para '{query}' ({len(results)})", border_style="cyan")
    table.add_column("Herramienta", style="bold green")
    table.add_column("Categoría", style="bold cyan")
    table.add_column("Descripción", style="white")

    for t in results:
        table.add_row(t.name, t.category, t.summary[:90] + ("..." if len(t.summary) > 90 else ""))

    console.print(table)


@tools_app.command(name="info", help="Muestra la sintaxis oficial, flags y ejemplos de una herramienta de Kali.")
def info_tool(
    name: str = typer.Argument(..., help="Nombre de la herramienta (ej. 'nmap', 'hydra', 'sqlmap')")
):
    """Muestra la ficha técnica completa de una herramienta."""
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.table import Table
    from coder_kali.tools_database import KaliToolsDatabase

    db = KaliToolsDatabase()
    tool = db.get_tool(name)

    if not tool:
        console.print(f"[red][!] La herramienta '{name}' no está en la base de datos local.[/red]")
        console.print(f"[dim]Puedes sincronizar la base completa con: blood-cipher tools sync[/dim]")
        return

    console.print()
    header_text = f"[bold green]{tool.name.upper()}[/bold green] - [cyan]{tool.category}[/cyan]\n[dim]{tool.url}[/dim]\n\n{tool.description}"
    console.print(Panel(header_text, title="📖 FICHA DE HERRAMIENTA KALI", border_style="bright_cyan"))

    if tool.usage_examples:
        console.print("\n[bold cyan]💡 Sintaxis y Ejemplos Oficiales:[/bold cyan]")
        for ex in tool.usage_examples:
            console.print(Panel(Syntax(ex, "bash", theme="monokai"), border_style="green", padding=(0, 1)))

    if tool.flags:
        table = Table(title="🚩 Parámetros & Flags Clave", border_style="yellow")
        table.add_column("Flag / Opción", style="bold yellow")
        table.add_column("Descripción", style="white")
        for flg, desc in tool.flags.items():
            table.add_row(flg, desc)
        console.print(table)


@tools_app.command(name="sync", help="Descarga y actualiza herramientas desde https://www.kali.org/tools/ y/o https://blackarch.org/tools.html.")
def sync_tools(
    source: str = typer.Option("all", "--source", "-s", help="Fuente a scrapear: 'kali', 'blackarch' o 'all' (ambas)"),
    limit: Optional[int] = typer.Option(None, "--limit", "-l", help="Limitar cantidad de herramientas a scrapear (útil para pruebas rápidas)")
):
    """Ejecuta el scraper en vivo contra los repositorios de Kali Linux y BlackArch Linux."""
    from coder_kali.tools_database import KaliToolsDatabase

    db = KaliToolsDatabase()
    src = source.lower().strip()

    if src in ["kali", "all"]:
        console.print("[bold cyan]Iniciando sincronización con el repositorio oficial de Kali Linux (kali.org)...[/bold cyan]")
        db.scrape_from_kali_org(limit=limit, verbose=True)

    if src in ["blackarch", "arch", "all"]:
        console.print("[bold cyan]Iniciando sincronización con el repositorio oficial de BlackArch Linux (blackarch.org)...[/bold cyan]")
        db.scrape_blackarch_org(limit=limit, verbose=True)


@app.command(name="update", help="Actualiza Blood-Cipher a la ultima version disponible desde GitHub.")
def update():
    """Descarga e instala la versión más reciente de Blood-Cipher desde el repositorio oficial."""
    import subprocess
    from pathlib import Path
    from rich.panel import Panel

    console.print()
    console.print(Panel("[bold cyan]Buscando actualizaciones de Blood-Cipher en GitHub...[/bold cyan]", border_style="cyan"))

    repo_dir = Path(__file__).resolve().parent.parent
    git_dir = repo_dir / ".git"

    if not git_dir.exists():
        console.print(f"[yellow][!] El directorio {repo_dir} no es un repositorio Git válido.[/yellow]")
        console.print("[dim]Puedes reinstalar con: git clone https://github.com/Sammir1209/blood-cipher.git && bash install.sh[/dim]")
        return

    try:
        # 1. git pull
        with console.status("[bold green]Descargando cambios desde origin/main...[/bold green]", spinner="dots"):
            pull_res = subprocess.run(
                ["git", "pull", "origin", "main"],
                cwd=str(repo_dir),
                capture_output=True,
                text=True,
                check=True,
            )

        output_str = pull_res.stdout.strip()
        if "Already up to date" in output_str or "Ya está actualizado" in output_str:
            console.print("[bold green][✓] Blood-Cipher ya está en la versión más reciente.[/bold green]")
        else:
            console.print("[bold green][✓] ¡Actualización descargada exitosamente![/bold green]")
            console.print(f"[dim]{output_str}[/dim]")

            # 2. Actualizar dependencias si es un entorno virtual
            venv_pip = Path.home() / ".local" / "share" / "blood-cipher" / "env" / "bin" / "pip"
            if venv_pip.exists():
                with console.status("[bold cyan]Actualizando dependencias del entorno virtual...[/bold cyan]", spinner="dots"):
                    subprocess.run(
                        [str(venv_pip), "install", "-r", str(repo_dir / "requirements.txt"), "--upgrade"],
                        capture_output=True,
                    )
                    subprocess.run(
                        [str(venv_pip), "install", "-e", str(repo_dir), "--no-deps"],
                        capture_output=True,
                    )

            console.print("[bold bright_green]🚀 ¡Blood-Cipher se ha actualizado correctamente![/bold bright_green]")

    except subprocess.CalledProcessError as e:
        console.print(f"[bold red][!] Error al actualizar desde Git: {e.stderr.strip()}[/bold red]")
    except Exception as ex:
        console.print(f"[bold red][!] Error inesperado durante la actualización: {ex}[/bold red]")


@app.command(name="reset", help="Restaura la configuración a los valores de fábrica.")
def reset():
    """Restablece la configuración."""
    config_mgr = ConfigManager()
    confirm = typer.confirm("¿Estás seguro de restablecer toda la configuración?")
    if confirm:
        config_mgr.reset()
        console.print("[bold green][✓] Configuración restablecida exitosamente.[/bold green]")


# ==============================================================================
# SUBCOMANDOS DE AUDITORÍA AVANZADA (Credenciales, Vulnerabilidades, Red)
# ==============================================================================

audit_app = typer.Typer(
    name="audit",
    help="Modulos de auditoria: Credenciales, Vulnerabilidades y Red.",
)
app.add_typer(audit_app, name="audit")


@audit_app.command(name="creds", help="Auditoria y cracking de credenciales, hashes y contrasenas.")
def audit_creds(
    hash_value: Optional[str] = typer.Option(None, "--hash", "-H", help="Hash individual a crackear."),
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Archivo de hashes o credenciales a procesar."),
    shadow: Optional[str] = typer.Option(None, "--shadow", help="Ruta al archivo /etc/shadow."),
    wordlist: str = typer.Option("/usr/share/wordlists/rockyou.txt", "--wordlist", "-w", help="Ruta al diccionario de contraseñas."),
    hash_type: Optional[str] = typer.Option(None, "--type", "-t", help="Tipo de hash (MD5, SHA1, SHA256, SHA512, NTLM, bcrypt)."),
    method: str = typer.Option("auto", "--method", "-m", help="Método: auto, native, john, hashcat."),
    analyze: Optional[str] = typer.Option(None, "--analyze", "-a", help="Analizar fortaleza de una contraseña."),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Guardar resultados en archivo (JSON o CSV)."),
):
    """Auditoría completa de credenciales y contraseñas."""
    from rich.panel import Panel
    from rich.table import Table
    from coder_kali.audit_modules import CredentialAuditor

    auditor = CredentialAuditor()

    # Modo: Analizar fortaleza de contraseña
    if analyze:
        result = auditor.analyze_password(analyze)
        grade_colors = {"A+": "bold green", "A": "green", "B": "cyan", "C": "yellow", "D": "red", "F": "bold red"}
        color = grade_colors.get(result.grade, "white")

        console.print()
        console.print(Panel(
            f"[bold white]Contraseña:[/bold white] {result.password}\n"
            f"[bold white]Longitud:[/bold white] {result.length}\n"
            f"[bold white]Entropía:[/bold white] {result.entropy} bits\n"
            f"[bold white]Puntuación:[/bold white] [{color}]{result.score}/100 ({result.grade})[/{color}]\n"
            f"[bold white]Mayúsculas:[/bold white] {'✅' if result.has_upper else '❌'} | "
            f"Minúsculas: {'✅' if result.has_lower else '❌'} | "
            f"Números: {'✅' if result.has_digits else '❌'} | "
            f"Especiales: {'✅' if result.has_special else '❌'}\n"
            f"[bold white]Común:[/bold white] {'⚠️ SÍ — aparece en diccionarios' if result.is_common else '✅ No'}\n\n"
            + "\n".join(result.feedback),
            title="[bold cyan]🔑 Análisis de Fortaleza de Contraseña[/bold cyan]",
            border_style="cyan",
        ))
        return

    # Modo: Parsear archivo de credenciales
    if file or shadow:
        target_file = shadow or file
        console.print(f"[bold cyan][*] Parseando archivo de credenciales: {target_file}[/bold cyan]")
        entries = auditor.parse_credentials_file(target_file)

        if entries and "error" in entries[0]:
            console.print(f"[bold red][!] {entries[0]['error']}[/bold red]")
            return

        table = Table(title=f"📋 Credenciales Parseadas de {Path(target_file).name}", border_style="cyan")
        table.add_column("#", style="dim", width=4)
        table.add_column("Usuario", style="bold green")
        table.add_column("Hash / Contraseña", style="white", max_width=50)
        table.add_column("Formato", style="cyan")
        table.add_column("Tipo Hash", style="yellow")

        for entry in entries:
            table.add_row(
                str(entry.get("line_number", "")),
                entry.get("username", "-"),
                (entry.get("hash", "") or entry.get("password", "") or entry.get("value", ""))[:50],
                entry.get("format", "unknown"),
                entry.get("hash_type", "-"),
            )

        console.print(table)

        # Ofrecer crackear los hashes encontrados
        hash_entries = [e for e in entries if e.get("hash")]
        if hash_entries:
            console.print(f"\n[bold green][*] {len(hash_entries)} hashes encontrados. Iniciando cracking automático...[/bold green]")
            results_table = Table(title="🔓 Resultados de Cracking", border_style="green")
            results_table.add_column("Hash", style="dim", max_width=35)
            results_table.add_column("Tipo", style="cyan")
            results_table.add_column("Contraseña", style="bold green")
            results_table.add_column("Tiempo", style="yellow")
            results_table.add_column("Estado", style="white")

            all_results = []
            for entry in hash_entries:
                h = entry["hash"]
                ht = entry.get("hash_type")
                console.print(f"[dim]  Crackeando: {h[:40]}... ({ht})[/dim]")
                result = auditor.crack_hash_native(h, wordlist_path=wordlist, hash_type=ht)
                all_results.append(result)

                status_str = "[bold green]✅ CRACKEADO[/bold green]" if result.status == "cracked" else "[dim red]❌ No encontrado[/dim red]"
                results_table.add_row(
                    h[:35],
                    result.hash_type,
                    result.cracked_password or "-",
                    f"{result.time_seconds}s",
                    status_str,
                )

            console.print(results_table)

            cracked = [r for r in all_results if r.status == "cracked"]
            console.print(f"\n[bold green][✓] {len(cracked)}/{len(all_results)} hashes crackeados exitosamente.[/bold green]")

            if output and all_results:
                fmt = "csv" if output.endswith(".csv") else "json"
                saved = auditor.export_results(all_results, output, fmt)
                console.print(f"[bold cyan][✓] Resultados exportados a: {saved}[/bold cyan]")

        return

    # Modo: Crackear hash individual
    if hash_value:
        identified = auditor.identify_hash(hash_value)
        console.print(f"\n[bold cyan][*] Hash detectado: {identified[0]['type']} (confianza: {identified[0]['confidence']})[/bold cyan]")

        if method == "auto" or method == "native":
            console.print(f"[bold green][*] Iniciando cracking nativo con diccionario: {wordlist}[/bold green]")
            with console.status("[bold cyan]Crackeando hash con Python nativo...[/bold cyan]", spinner="dots"):
                result = auditor.crack_hash_native(hash_value, wordlist_path=wordlist, hash_type=hash_type)
        elif method == "john":
            console.print("[bold green][*] Usando John the Ripper...[/bold green]")
            result = auditor.crack_with_john(hash_value, wordlist_path=wordlist, hash_format=hash_type)
        elif method == "hashcat":
            console.print("[bold green][*] Usando Hashcat...[/bold green]")
            result = auditor.crack_with_hashcat(hash_value, wordlist_path=wordlist)
        else:
            console.print(f"[red][!] Método desconocido: {method}[/red]")
            return

        if result.status == "cracked":
            console.print(Panel(
                f"[bold white]Hash:[/bold white] {result.original_hash}\n"
                f"[bold white]Tipo:[/bold white] {result.hash_type}\n"
                f"[bold green]Contraseña:[/bold green] [bold bright_green]{result.cracked_password}[/bold bright_green]\n"
                f"[bold white]Tiempo:[/bold white] {result.time_seconds}s\n"
                f"[bold white]Método:[/bold white] {result.method}",
                title="[bold green]🔓 ¡HASH CRACKEADO EXITOSAMENTE![/bold green]",
                border_style="green",
            ))
        else:
            console.print(Panel(
                f"[bold white]Hash:[/bold white] {result.original_hash}\n"
                f"[bold white]Tipo:[/bold white] {result.hash_type}\n"
                f"[bold white]Estado:[/bold white] [bold red]{result.status}[/bold red]\n"
                f"[bold white]Tiempo:[/bold white] {result.time_seconds}s\n"
                f"[bold white]Método:[/bold white] {result.method}",
                title="[bold red]🔒 Hash no crackeado[/bold red]",
                border_style="red",
            ))

        if output:
            fmt = "csv" if output.endswith(".csv") else "json"
            saved = auditor.export_results([result], output, fmt)
            console.print(f"[bold cyan][✓] Resultados exportados a: {saved}[/bold cyan]")
        return

    # Modo interactivo si no se pasan flags
    _interactive_creds_menu()


def _interactive_creds_menu():
    """Menú interactivo de auditoría de credenciales."""
    import questionary
    from rich.panel import Panel
    from coder_kali.audit_modules import CredentialAuditor

    auditor = CredentialAuditor()

    while True:
        console.print("\n[bold cyan]🔑 Auditoría de Credenciales — Menú Interactivo[/bold cyan]")

        action = questionary.select(
            "¿Qué operación deseas realizar?",
            choices=[
                questionary.Choice("🔓 Crackear un hash", value="CRACK"),
                questionary.Choice("📄 Parsear archivo de credenciales", value="PARSE"),
                questionary.Choice("🔍 Identificar tipo de hash", value="IDENTIFY"),
                questionary.Choice("📊 Analizar fortaleza de contraseña", value="ANALYZE"),
                questionary.Choice("🔙 Volver", value="BACK"),
            ],
        ).ask()

        if not action or action == "BACK":
            break

        if action == "CRACK":
            hash_input = questionary.text("Ingresa el hash a crackear:").ask()
            if hash_input:
                identified = auditor.identify_hash(hash_input.strip())
                console.print(f"[cyan]Tipo detectado: {identified[0]['type']}[/cyan]")
                with console.status("[bold cyan]Crackeando...[/bold cyan]", spinner="dots"):
                    result = auditor.crack_hash_native(hash_input.strip())
                if result.status == "cracked":
                    console.print(f"[bold green]✅ Contraseña encontrada: {result.cracked_password} ({result.time_seconds}s)[/bold green]")
                else:
                    console.print(f"[bold red]❌ No se encontró la contraseña ({result.time_seconds}s)[/bold red]")

        elif action == "PARSE":
            file_path = questionary.text("Ruta al archivo de credenciales:").ask()
            if file_path:
                entries = auditor.parse_credentials_file(file_path.strip())
                for e in entries[:20]:
                    console.print(f"  [{e.get('format', '?')}] {e.get('username', '-')} : {(e.get('hash', '') or e.get('password', ''))[:50]} ({e.get('hash_type', '-')})")

        elif action == "IDENTIFY":
            hash_input = questionary.text("Ingresa el hash a identificar:").ask()
            if hash_input:
                results = auditor.identify_hash(hash_input.strip())
                for r in results:
                    console.print(f"  [{r['confidence'].upper()}] {r['type']} — John: {r['john_format']} | Hashcat: -m {r['hashcat_mode']}")

        elif action == "ANALYZE":
            pw = questionary.text("Ingresa la contraseña a analizar:").ask()
            if pw:
                result = auditor.analyze_password(pw)
                console.print(f"  Puntuación: {result.score}/100 ({result.grade}) | Entropía: {result.entropy} bits")
                for fb in result.feedback:
                    console.print(f"  {fb}")


@audit_app.command(name="vulns", help="Escaneo de vulnerabilidades, SSL/TLS, cabeceras y CMS.")
def audit_vulns(
    target: str = typer.Argument(..., help="Dominio o IP objetivo a auditar."),
    severity: str = typer.Option("critical,high,medium", "--severity", "-s", help="Severidades a filtrar (critical,high,medium,low,info)."),
    scanner: str = typer.Option("all", "--scanner", help="Scanner específico: nuclei, nikto, ssl, headers, cms, all."),
    full: bool = typer.Option(False, "--full", help="Ejecutar auditoría completa con todos los scanners."),
):
    """Escaneo de vulnerabilidades con múltiples herramientas."""
    from rich.panel import Panel
    from rich.table import Table
    from coder_kali.audit_modules import VulnerabilityScanner

    vuln_scanner = VulnerabilityScanner()

    console.print(f"\n[bold cyan]🛡️ Iniciando auditoría de vulnerabilidades: {target}[/bold cyan]")

    results = []

    if full or scanner == "all":
        with console.status("[bold cyan]Ejecutando auditoría completa...[/bold cyan]", spinner="dots"):
            results = vuln_scanner.quick_vuln_scan(target)
    elif scanner == "nuclei":
        with console.status("[bold cyan]Escaneando con Nuclei...[/bold cyan]", spinner="dots"):
            results.append(vuln_scanner.nuclei_scan(target, severity=severity))
    elif scanner == "nikto":
        with console.status("[bold cyan]Escaneando con Nikto...[/bold cyan]", spinner="dots"):
            results.append(vuln_scanner.nikto_scan(target))
    elif scanner == "ssl":
        with console.status("[bold cyan]Auditando SSL/TLS...[/bold cyan]", spinner="dots"):
            results.append(vuln_scanner.ssl_audit(target))
    elif scanner == "headers":
        with console.status("[bold cyan]Analizando cabeceras HTTP...[/bold cyan]", spinner="dots"):
            results.append(vuln_scanner.header_analysis(target))
    elif scanner == "cms":
        with console.status("[bold cyan]Detectando CMS...[/bold cyan]", spinner="dots"):
            results.append(vuln_scanner.cms_detection(target))

    sev_colors = {"critical": "bold red", "high": "red", "medium": "yellow", "low": "cyan", "info": "dim", "error": "dim red"}

    for r in results:
        color = sev_colors.get(r.severity, "white")
        console.print(Panel(
            f"[bold white]Scanner:[/bold white] {r.scanner.upper()}\n"
            f"[bold white]Severidad:[/bold white] [{color}]{r.severity.upper()}[/{color}]\n"
            f"[bold white]Título:[/bold white] {r.title}\n"
            + (f"[bold white]Descripción:[/bold white] {r.description}\n" if r.description else "")
            + f"\n[dim]--- Salida ---[/dim]\n{r.raw_output[:2000]}",
            title=f"[{color}]{'⚠️' if r.severity in ['critical', 'high'] else '🔍'} {r.title}[/{color}]",
            border_style=color.replace("bold ", ""),
        ))

    console.print(f"\n[bold green][✓] Auditoría completada. {len(results)} scanners ejecutados sobre {target}.[/bold green]")


@audit_app.command(name="network", help="Pruebas de red: escaneo de puertos, hosts, DNS, OS detection.")
def audit_network(
    target: str = typer.Argument(..., help="IP, rango CIDR o dominio objetivo."),
    scan_type: str = typer.Option("ports", "--type", "-t", help="Tipo: ports, discovery, services, os, dns, traceroute, arp."),
    ports: str = typer.Option("top1000", "--ports", "-p", help="Puertos: top100, top1000, full, o rango (ej. 1-1000)."),
    timing: str = typer.Option("T4", "--timing", help="Timing template de Nmap: T0 a T5."),
    nmap_type: str = typer.Option("syn", "--nmap-type", help="Tipo de scan Nmap: syn, connect, udp, fin, xmas."),
    interface: str = typer.Option("eth0", "--iface", "-i", help="Interfaz de red para ARP scan."),
):
    """Pruebas y auditoría de red con múltiples técnicas."""
    from rich.panel import Panel
    from coder_kali.audit_modules import NetworkAuditor

    net_auditor = NetworkAuditor()

    console.print(f"\n[bold cyan]🌐 Auditoría de red: {target} (tipo: {scan_type})[/bold cyan]")

    result = None

    if scan_type == "ports":
        with console.status(f"[bold cyan]Escaneando puertos ({ports}) en {target}...[/bold cyan]", spinner="dots"):
            result = net_auditor.advanced_port_scan(
                target, ports=ports, scan_type=nmap_type,
                timing=timing, service_detect=True,
            )
    elif scan_type == "discovery":
        with console.status(f"[bold cyan]Descubriendo hosts en {target}...[/bold cyan]", spinner="dots"):
            result = net_auditor.host_discovery(target)
    elif scan_type == "services":
        with console.status(f"[bold cyan]Enumerando servicios en {target}...[/bold cyan]", spinner="dots"):
            result = net_auditor.service_enumeration(target)
    elif scan_type == "os":
        with console.status(f"[bold cyan]Detectando sistema operativo de {target}...[/bold cyan]", spinner="dots"):
            result = net_auditor.os_detection(target)
    elif scan_type == "dns":
        with console.status(f"[bold cyan]Enumerando DNS de {target}...[/bold cyan]", spinner="dots"):
            result = net_auditor.dns_enumeration(target)
    elif scan_type == "traceroute":
        with console.status(f"[bold cyan]Ejecutando traceroute a {target}...[/bold cyan]", spinner="dots"):
            result = net_auditor.traceroute_analysis(target)
    elif scan_type == "arp":
        with console.status(f"[bold cyan]Ejecutando ARP scan en {interface}...[/bold cyan]", spinner="dots"):
            result = net_auditor.arp_scan(interface=interface)
    else:
        console.print(f"[red][!] Tipo de scan desconocido: {scan_type}[/red]")
        return

    if result:
        console.print(Panel(
            f"[bold white]Objetivo:[/bold white] {result.target}\n"
            f"[bold white]Tipo:[/bold white] {result.scan_type}\n\n"
            f"{result.raw_output[:3000]}",
            title=f"[bold cyan]🌐 Resultado: {result.scan_type.upper()}[/bold cyan]",
            border_style="cyan",
        ))

        if result.parsed_data:
            if "open_ports" in result.parsed_data and result.parsed_data["open_ports"]:
                console.print(f"\n[bold green][✓] Puertos abiertos encontrados: {', '.join(result.parsed_data['open_ports'])}[/bold green]")
            if "hosts" in result.parsed_data:
                console.print(f"[bold green][✓] Hosts activos: {result.parsed_data.get('total', len(result.parsed_data['hosts']))}[/bold green]")



# ==============================================================================
# SUBCOMANDOS MULTI-VPN Y PRIVACIDAD OPSEC
# ==============================================================================
vpn_app = typer.Typer(
    name="vpn",
    help="🛡️ Gestor Multi-VPN y Privacidad (Surfshark, NordVPN, ProtonVPN, Mullvad, Custom, Tor).",
    invoke_without_command=True,
)
app.add_typer(vpn_app, name="vpn")


@vpn_app.callback()
def vpn_default(ctx: typer.Context):
    """Si se llama a 'blood-cipher vpn' sin subcomando, abre el menú interactivo."""
    if ctx.invoked_subcommand is None:
        from coder_kali.ui.vpn_menu import interactive_vpn_menu
        interactive_vpn_menu()


@vpn_app.command(name="status", help="Muestra el estado actual del túnel, interfaz de red e IP pública.")
def vpn_status():
    """Consulta la IP pública y estado de la VPN."""
    from coder_kali.vpn_manager import VPNManager
    from coder_kali.ui.vpn_menu import render_vpn_status_card
    mgr = VPNManager()
    render_vpn_status_card(mgr)


@vpn_app.command(name="connect", help="Conecta a un proveedor de VPN (Surfshark, NordVPN, Proton, Custom).")
def vpn_connect(
    provider: str = typer.Argument("surfshark", help="Proveedor de VPN (surfshark, nordvpn, protonvpn, custom)"),
    location: Optional[str] = typer.Option("es-mad", "--location", "-l", help="Código de ubicación (ej: es-mad, us-nyc, de-fra)"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Ruta directa a un archivo .ovpn"),
    daemon: bool = typer.Option(True, "--daemon/--no-daemon", help="Ejecutar en segundo plano como servicio."),
):
    """Inicia el túnel VPN en segundo plano."""
    from coder_kali.vpn_manager import VPNManager
    mgr = VPNManager()
    with console.status(f"[bold cyan]Estableciendo conexión VPN con {provider}...[/bold cyan]", spinner="dots"):
        success, msg = mgr.connect(provider, config_path=config, location_code=location, daemon=daemon)
    if success:
        console.print(f"[bold green][✓] {msg}[/bold green]")
    else:
        console.print(f"[bold red][!] {msg}[/bold red]")


@vpn_app.command(name="disconnect", help="Desconecta cualquier túnel VPN activo de Blood-Cipher.")
def vpn_disconnect():
    """Detiene el túnel VPN activo."""
    from coder_kali.vpn_manager import VPNManager
    mgr = VPNManager()
    with console.status("[bold yellow]Desconectando túnel VPN...[/bold yellow]", spinner="dots"):
        success, msg = mgr.disconnect()
    console.print(f"[bold cyan]{msg}[/bold cyan]")


@vpn_app.command(name="list", help="Lista las ubicaciones y perfiles disponibles para un proveedor.")
def vpn_list(
    provider: str = typer.Argument("surfshark", help="Proveedor a consultar (surfshark, nordvpn, protonvpn)")
):
    """Muestra servidores disponibles."""
    from rich.table import Table
    from coder_kali.vpn_manager import VPNManager, VPN_PROVIDERS
    mgr = VPNManager()
    meta = VPN_PROVIDERS.get(provider)
    if not meta:
        console.print(f"[red][!] Proveedor '{provider}' no reconocido.[/red]")
        return

    table = Table(title=f"📍 Servidores y Ubicaciones para {meta['name']}", border_style="cyan")
    table.add_column("Código", style="bold green")
    table.add_column("Ubicación", style="white")

    pop = meta.get("popular_locations", [])
    for row in pop:
        table.add_row(row[0], row[1])

    console.print(table)
    local_files = mgr.list_available_ovpn_files(provider)
    if local_files:
        console.print(f"\n[bold green][✓] Perfiles .ovpn descargados localmente:[/bold green] {len(local_files)}")


@vpn_app.command(name="test", help="Verifica si las APIs de IA son accesibles a través de la VPN actual.")
def vpn_test():
    """Prueba la salud de las APIs de IA con la conexión actual."""
    from rich.table import Table
    from coder_kali.vpn_manager import VPNManager
    mgr = VPNManager()
    with console.status("[bold cyan]Comprobando conectividad con proveedores de IA...[/bold cyan]", spinner="dots"):
        results = mgr.check_ai_health()

    table = Table(title="🧠 Estado de Conectividad con APIs de IA", border_style="cyan")
    table.add_column("Servicio de IA", style="bold white")
    table.add_column("Estado de Conexión", style="bold")

    for name, ok in results.items():
        table.add_row(name, "[green]✓ Accesible[/green]" if ok else "[red]✗ Inaccesible[/red]")

    console.print(table)


def main():
    app()


if __name__ == "__main__":
    main()

