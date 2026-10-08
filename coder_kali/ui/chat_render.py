"""
coder_kali/ui/chat_render.py - Renderizador TUI de Élite con Rich.
Muestra banners, paneles cyberpunk, respuestas Markdown, bloques de código
y resultados de comandos estilizados.
"""

import sys
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text
from rich.syntax import Syntax
from rich.box import ROUNDED, DOUBLE, HEAVY

console = Console()

BANNER_ART_LINUX = r"""
  ██████╗ ██╗      ██████╗  ██████╗ ██████╗       ██████╗██╗██████╗ ██╗  ██╗███████╗██████╗ 
  ██╔══██╗██║     ██╔═══██╗██╔═══██╗██╔══██╗     ██╔════╝██║██╔══██╗██║  ██║██╔════╝██╔══██╗
  ██████╔╝██║     ██║   ██║██║   ██║██║  ██║     ██║     ██║██████╔╝███████║█████╗  ██████╔╝
  ██╔══██╗██║     ██║   ██║██║   ██║██║  ██║     ██║     ██║██╔═══╝ ██╔══██║██╔══╝  ██╔══██╗
  ██████╔╝███████╗╚██████╔╝╚██████╔╝██████╔╝     ╚██████╗██║██║     ██║  ██║███████╗██║  ██║
  ╚═════╝ ╚══════╝ ╚═════╝  ╚═════╝ ╚═════╝       ╚═════╝╚═╝╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
"""

BANNER_ART_WINDOWS = r"""
  ██████╗ ██╗      ██████╗  ██████╗ ██████╗       ██╗    ██╗██╗███╗   ██╗██████╗  ██████╗ ██╗    ██╗███████╗
  ██╔══██╗██║     ██╔═══██╗██╔═══██╗██╔══██╗     ██║    ██║██║████╗  ██║██╔══██╗██╔═══██╗██║    ██║██╔════╝
  ██████╔╝██║     ██║   ██║██║   ██║██║  ██║     ██║ █╗ ██║██║██╔██╗ ██║██║  ██║██║   ██║██║ █╗ ██║███████╗
  ██╔══██╗██║     ██║   ██║██║   ██║██║  ██║     ██║███╗██║██║██║╚██╗██║██║  ██║██║   ██║██║███╗██║╚════██║
  ██████╔╝███████╗╚██████╔╝╚██████╔╝██████╔╝     ╚███╔███╔╝██║██║ ╚████║██████╔╝╚██████╔╝╚███╔███╔╝███████║
  ╚═════╝ ╚══════╝ ╚═════╝  ╚═════╝ ╚═════╝       ╚══╝╚══╝ ╚═╝╚═╝  ╚═══╝╚═════╝  ╚═════╝  ╚══╝╚══╝ ╚══════╝
"""


def print_banner(version: str = "2.0.0", provider: str = "gemini", model: str = "gemini-2.0-flash", scope: Optional[str] = None, key_pool_size: int = 1, workspace: Optional[str] = None):
    """Imprime el banner temático adaptado para Windows o Linux."""
    import platform
    is_windows = platform.system() == "Windows"

    if is_windows:
        console.print(f"[bold deep_sky_blue1]{BANNER_ART_WINDOWS}[/bold deep_sky_blue1]")
        header_title = "[bold deep_sky_blue1]● SISTEMA DE OPERACIONES TÁCTICAS IA — WINDOWS ELITE[/bold deep_sky_blue1]"
        border_style = "deep_sky_blue1"
        os_label = "v" + version + " [Windows Native / PowerShell Host]"
    else:
        console.print(f"[bold red]{BANNER_ART_LINUX}[/bold red]")
        header_title = "[bold green]● SISTEMA DE OPERACIONES TÁCTICAS IA — KALI LINUX[/bold green]"
        border_style = "bright_blue"
        os_label = "v" + version + " [Linux Native / Kali]"

    info_table = Table.grid(padding=(0, 2))
    info_table.add_column(style="bold bright_green" if not is_windows else "bold bright_cyan")
    info_table.add_column(style="bold white")

    info_table.add_row("⚡ Versión:", os_label)
    provider_str = f"[cyan]{provider.upper()}[/cyan]"
    if key_pool_size > 1:
        provider_str += f"  [bold green]🔄 {key_pool_size} API Keys en rotación[/bold green]"
    info_table.add_row("🤖 Proveedor IA:", provider_str)
    info_table.add_row("🧠 Modelo Activo:", f"[yellow]{model}[/yellow]")
    if workspace:
        info_table.add_row("📂 Workspace Sesión:", f"[cyan]{workspace}[/cyan]")
    info_table.add_row("🎯 Alcance / SOW:", f"[bold green]{scope}[/bold green]" if scope else "[dim]No definido ('scope' para cargar)[/dim]")
    info_table.add_row("🛡️  Modo de Shell:", "[bold cyan]PowerShell 5.1/7+ Seguro[/bold cyan]" if is_windows else "[green]Supervisión PTY Activa (sudo)[/green]")
    info_table.add_row("💡 Comandos Rápidos:", "[dim]escribe 'exit', 'scope', 'config', 'clear' o 'ayuda'[/dim]")

    panel = Panel(
        info_table,
        title=header_title,
        border_style=border_style,
        box=ROUNDED,
        padding=(0, 2),
    )
    console.print(panel)
    console.print()


def render_user_message(message: str):
    """Renderiza el mensaje del operador con estilo CLI minimalista y elegante."""
    import platform
    is_windows = platform.system() == "Windows"

    console.print()
    badge_title = "❯ OPERADOR (WINDOWS)" if is_windows else "❯ OPERADOR (KALI)"
    badge = Text(f" {badge_title} ", style="bold white on #1e293b")
    console.print(badge)
    panel = Panel(
        Text(message, style="bold white"),
        border_style="#38bdf8" if is_windows else "#4ade80",
        box=ROUNDED,
        padding=(0, 2),
    )
    console.print(panel)


def render_ai_message(message: str):
    """Renderiza la respuesta directa de Blood-Cipher en formato Markdown de élite con estética Claude/Gemini."""
    import re
    import platform
    is_windows = platform.system() == "Windows"

    # 1. Eliminar etiquetas de razonamiento/pensamiento
    cleaned_text = re.sub(r'<think>[\s\S]*?</think>', '', message, flags=re.IGNORECASE)
    cleaned_text = re.sub(r'```(?:thought|thinking|reasoning)[\s\S]*?```', '', cleaned_text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r'^\s*<think>[\s\S]*$', '', cleaned_text, flags=re.IGNORECASE)
    
    # 2. Filtrar las etiquetas XML de comandos completas o truncadas/abiertas
    raw_for_preview = cleaned_text
    cleaned_text = re.sub(r'<ejecutar_comando>[\s\S]*?</ejecutar_comando>', '', cleaned_text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r'<escribir_archivo[^>]*>[\s\S]*?</escribir_archivo>', '', cleaned_text, flags=re.IGNORECASE)
    # Limpiar posibles etiquetas no cerradas si la respuesta se truncó
    cleaned_text = re.sub(r'<ejecutar_comando>[\s\S]*$', '', cleaned_text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r'<escribir_archivo[^>]*>[\s\S]*$', '', cleaned_text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r'</?(?:ejecutar_comando|escribir_archivo)[^>]*>', '', cleaned_text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text).strip()

    # 3. Si no hay texto conversacional pero sí hay comandos, extraer un resumen descriptivo
    if not cleaned_text.strip():
        xml_cmds = re.findall(r'<ejecutar_comando>([\s\S]*?)(?:</ejecutar_comando>|$)', raw_for_preview, flags=re.IGNORECASE)
        if not xml_cmds:
            xml_cmds = re.findall(r'<ejecutar_comando>([\s\S]*?)(?:</ejecutar_comando>|$)', message, flags=re.IGNORECASE)
        if xml_cmds:
            cmd_lines = [c.strip().split('\n')[0] for c in xml_cmds if c.strip()]
            cleaned_text = "⚡ **Acciones Tácticas en Proceso:**\n" + "\n".join([f"- `{cmd}`" for cmd in cmd_lines[:6]])
        else:
            return

    console.print()
    header_title = "✦ BLOOD-CIPHER [WINDOWS COPILOT]" if is_windows else "✦ BLOOD-CIPHER [KALI COPILOT]"
    header_style = "bold white on #0284c7" if is_windows else "bold white on #059669"
    border_style = "#0ea5e9" if is_windows else "#10b981"

    header = Text(f" {header_title} ", style=header_style)
    console.print(header)

    md = Markdown(cleaned_text, code_theme="monokai", hyperlinks=True)
    panel = Panel(
        md,
        border_style=border_style,
        box=ROUNDED,
        padding=(1, 2),
    )
    console.print(panel)


def render_execution_result(result, command: Optional[str] = None):
    """Muestra el resultado de la ejecución del comando o escritura de archivo."""
    console.print()
    if result.was_rejected:
        panel = Panel(
            Text(result.output, style="bold red"),
            title="[bold red]⛔ ACCIÓN CANCELADA POR EL OPERADOR[/bold red]",
            border_style="red",
            box=ROUNDED,
        )
        console.print(panel)
        return

    if result.is_file_op:
        title = f"[bold bright_green]✓ SCRIPT GENERADO CON ÉXITO: {result.target_path}[/bold bright_green]" if result.success else f"[bold red]✗ ERROR EN ARCHIVO: {result.target_path}[/bold red]"
        border_color = "bright_green" if result.success else "bright_red"
        panel = Panel(
            Text(result.output, style="white"),
            title=title,
            border_style=border_color,
            box=ROUNDED,
            padding=(0, 2),
        )
        console.print(panel)
        return

    # Para comandos de terminal
    title = f"[bold bright_green]✓ SALIDA TÁCTICA DE SISTEMA (Código {result.returncode})[/bold bright_green]" if result.success else f"[bold bright_red]✗ ERROR DE EJECUCIÓN (Código {result.returncode})[/bold bright_red]"
    border_color = "bright_green" if result.success else "bright_red"

    output_text = result.output
    lines = output_text.splitlines()

    safe_lines = []
    for l in lines[:70]:
        if len(l) > 350:
            safe_lines.append(l[:347] + "...")
        else:
            safe_lines.append(l)

    if len(lines) > 60:
        preview = "\n".join(safe_lines[:40]) + f"\n\n[dim cyan]... [{len(lines) - 50} líneas intermedias omitidas] ...[/dim cyan]\n\n" + "\n".join([l[:350] for l in lines[-10:]])
        display_content = preview
    elif len(output_text) > 6000:
        display_content = "\n".join(safe_lines[:40]) + f"\n\n[dim cyan]... [Salida extensa: {len(output_text)} caracteres] ...[/dim cyan]\n"
    else:
        display_content = "\n".join(safe_lines)

    panel = Panel(
        Text(display_content, style="white"),
        title=title,
        border_style=border_color,
        box=ROUNDED,
        padding=(0, 2),
        subtitle=f"[bold yellow]$ {command or ''}[/bold yellow]",
    )
    console.print(panel)


def render_error(title: str, details: str):
    """Muestra una caja de error visual."""
    console.print()
    content = f"[bold red]{title}[/bold red]\n\n[white]{details}[/white]"
    panel = Panel(
        content,
        title="[bold red]🚨 ALERTA DEL SISTEMA[/bold red]",
        border_style="bright_red",
        box=HEAVY,
        padding=(1, 2),
    )
    console.print(panel)


def render_info(message: str):
    """Muestra un mensaje informativo estilizado."""
    console.print(f"[bold cyan][*][/bold cyan] [white]{message}[/white]")


def render_agent_cooperation(agent_role: str, agent_name: str, message: str):
    """Muestra la intervención de un sub-agente táctico especializado (ej. Recon, Exploit, Auditor)."""
    console.print()
    badge = Text(f" 🤝 ENLACE MULTI-AGENTE: {agent_role.upper()} [{agent_name}] ", style="bold black on bright_yellow")
    console.print(badge)
    panel = Panel(
        Text(message, style="bold bright_white"),
        title=f"[bold yellow]⚡ {agent_name} en operación coordinada[/bold yellow]",
        border_style="yellow",
        box=ROUNDED,
        padding=(0, 2),
    )
    console.print(panel)


def render_background_action(action_type: str, detail: str, status: str = "PROCESANDO EN SEGUNDO PLANO"):
    """Muestra un indicador estilizado de procesamiento en segundo plano."""
    console.print()
    border_color = "bright_blue"
    badge_title = f"[bold cyan]⚡ {status}[/bold cyan]"
    content = f"[bold white]{action_type}:[/bold white] [bright_cyan]{detail}[/bright_cyan]\n[dim](El sistema sigue ejecutando en background. La terminal está protegida contra entradas accidentales)[/dim]"
    panel = Panel(
        content,
        title=badge_title,
        border_style=border_color,
        box=ROUNDED,
        padding=(0, 2),
    )
    console.print(panel)


def render_system_status(status_dict: dict):
    """Renderiza una tabla con el estado del sistema y herramientas de diagnóstico."""
    table = Table(title="📊 Estado de Blood-Cipher", box=ROUNDED, border_style="cyan")
    table.add_column("Propiedad", style="bold cyan")
    table.add_column("Valor", style="white")

    for k, v in status_dict.items():
        table.add_row(k, str(v))

    console.print()
    console.print(table)
    console.print()
