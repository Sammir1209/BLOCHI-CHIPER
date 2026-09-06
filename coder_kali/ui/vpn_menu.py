"""
coder_kali/ui/vpn_menu.py - Menú Interactivo Táctico de Gestión Multi-VPN y Privacidad.
Interfaz Questionary + Rich para conectar, desconectar y diagnosticar VPNs y estado de IP.
"""

from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import questionary

from coder_kali.vpn_manager import VPNManager, VPN_PROVIDERS

console = Console()


def render_vpn_status_card(vpn_mgr: VPNManager):
    """Muestra un panel enriquecido con el estado actual de la red y la IP."""
    active, iface, pid = vpn_mgr.is_vpn_active()
    with console.status("[bold cyan]Consultando estado de red e IP pública...[/bold cyan]", spinner="dots"):
        ip_info = vpn_mgr.get_public_ip_info(timeout=3.5)

    status_badge = "[bold green]● CONECTADO Y PROTEGIDO[/bold green]" if active else "[bold yellow]○ DESCONECTADO (Conexión Directa)[/bold yellow]"
    iface_str = f"[bold cyan]{iface}[/bold cyan]" if iface else "[dim]Ninguna[/dim]"
    pid_str = f"[dim](PID: {pid})[/dim]" if pid else ""

    content = (
        f"[bold white]Estado:[/bold white] {status_badge} {pid_str}\n"
        f"[bold white]Interfaz Activa:[/bold white] {iface_str}\n"
        f"[bold white]IP Pública:[/bold white] [bold bright_green]{ip_info.get('ip')}[/bold bright_green]\n"
        f"[bold white]Ubicación:[/bold white] {ip_info.get('city') + ', ' if ip_info.get('city') else ''}{ip_info.get('country')}\n"
        f"[bold white]Organización / ISP:[/bold white] [dim]{ip_info.get('org')}[/dim]"
    )

    console.print(Panel(
        content,
        title="[bold cyan]🛡️ ESTADO DE RED & PRIVACIDAD OPSEC[/bold cyan]",
        border_style="green" if active else "yellow",
    ))


def interactive_vpn_menu(vpn_mgr: Optional[VPNManager] = None):
    """Menú interactivo completo para gestionar conexiones VPN."""
    if vpn_mgr is None:
        vpn_mgr = VPNManager()

    while True:
        console.print("")
        render_vpn_status_card(vpn_mgr)

        active, _, _ = vpn_mgr.is_vpn_active()

        choices = []
        if not active:
            choices.append(questionary.Choice("🚀 Conectar a una VPN (Surfshark, NordVPN, Proton, etc.)", value="CONNECT"))
        else:
            choices.append(questionary.Choice("🛑 Desconectar VPN activa", value="DISCONNECT"))
            choices.append(questionary.Choice("🔄 Cambiar de servidor o país", value="RECONNECT"))

        choices.extend([
            questionary.Choice("🔑 Configurar credenciales de proveedor", value="CREDS"),
            questionary.Choice("🧪 Probar conectividad con APIs de IA", value="AI_TEST"),
            questionary.Choice("📁 Importar perfil .ovpn personalizado (Lab / HTB / VPS)", value="CUSTOM_OVPN"),
            questionary.Choice("🧅 Modo Tor SOCKS5 (Verificar servicio)", value="TOR"),
            questionary.Choice("⬅️ Volver", value="BACK"),
        ])

        action = questionary.select(
            "¿Qué acción táctica de red deseas ejecutar?",
            choices=choices,
        ).ask()

        if not action or action == "BACK":
            break

        elif action in ["CONNECT", "RECONNECT"]:
            if action == "RECONNECT":
                with console.status("[bold yellow]Desconectando túnel actual...[/bold yellow]", spinner="dots"):
                    vpn_mgr.disconnect()

            # Seleccionar proveedor
            prov_choices = [
                questionary.Choice(f"🦈 {meta['name']} ({meta.get('protocol', '').upper()})", value=key)
                for key, meta in VPN_PROVIDERS.items() if key != "tor"
            ]

            selected_provider = questionary.select(
                "Selecciona tu proveedor de VPN:",
                choices=prov_choices,
            ).ask()

            if not selected_provider:
                continue

            # Si es Surfshark o proveedor con descarga
            if selected_provider == "surfshark":
                # Comprobar credenciales
                creds = vpn_mgr.get_credentials("surfshark")
                if not creds:
                    console.print("[yellow][!] No hay credenciales de servicio guardadas para Surfshark.[/yellow]")
                    console.print("[dim]Puedes obtenerlas en https://my.surfshark.com/vpn/manual-setup/main[/dim]")
                    user = questionary.text("Ingresa tu Username de servicio de Surfshark:").ask()
                    pwd = questionary.password("Ingresa tu Password de servicio de Surfshark:").ask()
                    if user and pwd:
                        vpn_mgr.save_credentials("surfshark", user, pwd)
                        console.print("[bold green][✓] Credenciales guardadas con permisos seguros.[/bold green]")
                    else:
                        console.print("[red][!] Cancelado.[/red]")
                        continue

                # Ubicaciones populares
                loc_choices = [
                    questionary.Choice(f"📍 {desc} [{code}]", value=code)
                    for code, desc, _ in VPN_PROVIDERS["surfshark"]["popular_locations"]
                ]
                loc_choices.append(questionary.Choice("🔍 Otra ubicación (Escribir código de país)", value="OTHER"))

                chosen_loc = questionary.select(
                    "Selecciona el nodo o país de salida:",
                    choices=loc_choices,
                ).ask()

                if chosen_loc == "OTHER":
                    chosen_loc = questionary.text("Código de país/ciudad (ej: de-fra, us-nyc, jp-tok):").ask()

                if not chosen_loc:
                    continue

                with console.status(f"[bold cyan]Estableciendo túnel con Surfshark [{chosen_loc}]...[/bold cyan]", spinner="dots"):
                    success, msg = vpn_mgr.connect("surfshark", location_code=chosen_loc, daemon=True)

                if success:
                    console.print(f"\n[bold green][✓] {msg}[/bold green]")
                else:
                    console.print(f"\n[bold red][!] {msg}[/bold red]")

            elif selected_provider == "custom":
                ovpn_path = questionary.path("Ruta al archivo .ovpn de tu servidor o laboratorio:").ask()
                if ovpn_path and Path(ovpn_path).exists():
                    with console.status("[bold cyan]Iniciando túnel OpenVPN personalizado...[/bold cyan]", spinner="dots"):
                        success, msg = vpn_mgr.connect("custom", config_path=ovpn_path, daemon=True)
                    if success:
                        console.print(f"\n[bold green][✓] {msg}[/bold green]")
                    else:
                        console.print(f"\n[bold red][!] {msg}[/bold red]")
                else:
                    console.print("[red][!] Archivo no encontrado.[/red]")

            else:
                console.print(f"[cyan][*] Preparando configuración para {selected_provider}...[/cyan]")
                existing = vpn_mgr.list_available_ovpn_files(selected_provider)
                if not existing:
                    vpn_mgr.download_provider_configs(selected_provider)
                    existing = vpn_mgr.list_available_ovpn_files(selected_provider)

                if existing:
                    file_choices = [questionary.Choice(f.name, value=str(f)) for f in existing[:20]]
                    chosen_file = questionary.select("Selecciona el perfil .ovpn:", choices=file_choices).ask()
                    if chosen_file:
                        with console.status("[bold cyan]Conectando túnel OpenVPN...[/bold cyan]", spinner="dots"):
                            success, msg = vpn_mgr.connect(selected_provider, config_path=chosen_file, daemon=True)
                        if success:
                            console.print(f"\n[bold green][✓] {msg}[/bold green]")
                        else:
                            console.print(f"\n[bold red][!] {msg}[/bold red]")
                else:
                    console.print(f"[yellow][!] Coloca tus archivos .ovpn en {vpn_mgr.get_provider_configs_dir(selected_provider)}[/yellow]")

        elif action == "DISCONNECT":
            with console.status("[bold yellow]Desconectando túnel VPN...[/bold yellow]", spinner="dots"):
                success, msg = vpn_mgr.disconnect()
            console.print(f"[bold cyan]{msg}[/bold cyan]")

        elif action == "CREDS":
            prov = questionary.select(
                "¿Para qué proveedor deseas guardar credenciales?",
                choices=["surfshark", "nordvpn", "protonvpn", "custom"],
            ).ask()
            if prov:
                u = questionary.text(f"Usuario de servicio para {prov}:").ask()
                p = questionary.password(f"Contraseña de servicio para {prov}:").ask()
                if u and p:
                    vpn_mgr.save_credentials(prov, u, p)
                    console.print(f"[bold green][✓] Credenciales para {prov} guardadas exitosamente.[/bold green]")

        elif action == "AI_TEST":
            with console.status("[bold cyan]Verificando conectividad con proveedores de IA...[/bold cyan]", spinner="dots"):
                health = vpn_mgr.check_ai_health()

            table = Table(title="🧠 Estado de Conectividad con APIs de IA", border_style="cyan")
            table.add_column("Servicio de IA", style="bold white")
            table.add_column("Estado de Red", style="bold")

            for name, ok in health.items():
                status = "[green]✓ Accesible (Sin bloqueo)[/green]" if ok else "[red]✗ Inaccesible o Filtrado[/red]"
                table.add_row(name, status)

            console.print(table)

        elif action == "CUSTOM_OVPN":
            src = questionary.path("Introduce la ruta de tu archivo .ovpn para guardarlo en Blood-Cipher:").ask()
            if src and Path(src).exists():
                custom_dir = vpn_mgr.get_provider_configs_dir("custom")
                dest = custom_dir / Path(src).name
                import shutil
                shutil.copyfile(src, dest)
                console.print(f"[bold green][✓] Perfil importado a:[/bold green] {dest}")

        elif action == "TOR":
            console.print(Panel(
                "[bold green]🧅 Modo Tor Network (SOCKS5)[/bold green]\n\n"
                "Para enrutar tráfico local a través de Tor:\n"
                "1. Asegúrate de tener Tor instalado: [bold cyan]sudo apt install -y tor[/bold cyan]\n"
                "2. Inicia el servicio: [bold cyan]sudo systemctl start tor[/bold cyan]\n"
                "3. El puerto SOCKS5 estará listo en: [bold bright_green]127.0.0.1:9050[/bold bright_green]\n"
                "4. Puedes verificarlo con: [bold cyan]curl --socks5 127.0.0.1:9050 https://check.torproject.org/api/ip[/bold cyan]",
                title="Información Tor SOCKS5",
                border_style="magenta",
            ))
