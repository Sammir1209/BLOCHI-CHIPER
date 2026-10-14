import os
import sys
import json
import webbrowser
from typing import Optional, List, Dict, Any
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from coder_kali.config import ConfigManager, DEFAULT_PROVIDERS
from coder_kali.model_discovery import fetch_live_models
from coder_kali.key_detector import detect_provider_and_models

console = Console()


def _run_web_config_portal(config_mgr: ConfigManager, port: int = 8999) -> bool:
    """Levanta un servidor web local estilizado para configurar Blood-Cipher visualmente."""
    saved_state = {"saved": False, "provider": "", "model": ""}

    class ConfigHTTPHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # Silenciar logs ruidosos

        def do_GET(self):
            if self.path == "/" or self.path.startswith("/?"):
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                
                # Opciones de proveedores
                curr_p = config_mgr.get_active_provider()
                curr_m = config_mgr.get_active_model()
                curr_k = config_mgr.get_api_key(curr_p) or ""
                curr_b = config_mgr.get_api_base(curr_p) or ""

                prov_options = ""
                for p_key, p_val in DEFAULT_PROVIDERS.items():
                    sel = "selected" if p_key == curr_p else ""
                    prov_options += f'<option value="{p_key}" {sel}>{p_val["name"]} ({p_key})</option>'

                providers_json = json.dumps(DEFAULT_PROVIDERS)
                current_config_json = json.dumps({
                    "active_provider": curr_p,
                    "active_model": curr_m,
                    "api_keys": config_mgr.config.get("api_keys", {}),
                    "api_bases": config_mgr.config.get("api_bases", {})
                })

                html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Blood-Cipher — Panel de Configuración</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;800&family=Outfit:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: rgba(17, 24, 39, 0.85);
            --primary: #00d2ff;
            --accent: #3a7bd5;
            --success: #00e676;
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
            --border-glow: rgba(0, 210, 255, 0.3);
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: radial-gradient(circle at top right, #111e38, #070a12 70%);
            color: var(--text-main);
            font-family: 'Outfit', sans-serif;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
        }}
        .container {{
            background: var(--card-bg);
            border: 1px solid var(--border-glow);
            backdrop-filter: blur(16px);
            border-radius: 16px;
            max-width: 680px;
            width: 100%;
            padding: 36px;
            box-shadow: 0 20px 50px rgba(0,0,0,0.6), 0 0 30px rgba(0, 210, 255, 0.15);
        }}
        .header {{
            display: flex;
            align-items: center;
            gap: 14px;
            margin-bottom: 24px;
            border-bottom: 1px solid rgba(255,255,255,0.08);
            padding-bottom: 18px;
        }}
        .badge {{
            background: linear-gradient(135deg, var(--primary), var(--accent));
            color: #000;
            font-weight: 800;
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 13px;
            letter-spacing: 1px;
            font-family: 'JetBrains Mono', monospace;
        }}
        h1 {{ font-size: 24px; font-weight: 700; color: #fff; }}
        p.subtitle {{ color: var(--text-muted); font-size: 14px; margin-top: 4px; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{
            display: block;
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--primary);
            margin-bottom: 8px;
            font-family: 'JetBrains Mono', monospace;
        }}
        select, input[type="text"], input[type="password"] {{
            width: 100%;
            background: rgba(10, 15, 26, 0.9);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 10px;
            padding: 12px 16px;
            color: #fff;
            font-size: 15px;
            font-family: 'JetBrains Mono', monospace;
            outline: none;
            transition: all 0.2s ease;
        }}
        select:focus, input:focus {{
            border-color: var(--primary);
            box-shadow: 0 0 12px rgba(0, 210, 255, 0.35);
        }}
        .helper {{ font-size: 12px; color: var(--text-muted); margin-top: 6px; }}
        .btn-group {{
            display: flex;
            gap: 12px;
            margin-top: 30px;
        }}
        button {{
            flex: 1;
            padding: 14px;
            border-radius: 10px;
            border: none;
            font-weight: 700;
            font-size: 15px;
            cursor: pointer;
            transition: all 0.2s ease;
            font-family: 'Outfit', sans-serif;
        }}
        .btn-primary {{
            background: linear-gradient(135deg, #00d2ff, #0072ff);
            color: #fff;
            box-shadow: 0 4px 20px rgba(0, 114, 255, 0.4);
        }}
        .btn-primary:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 25px rgba(0, 210, 255, 0.6);
        }}
        .status-box {{
            padding: 14px;
            border-radius: 10px;
            margin-top: 20px;
            display: none;
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
        }}
        .status-box.success {{
            background: rgba(0, 230, 118, 0.15);
            border: 1px solid var(--success);
            color: var(--success);
            display: block;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="badge">BLOOD-CIPHER</div>
            <div>
                <h1>Configurador Web Visual</h1>
                <p class="subtitle">Selecciona tu proveedor, pega tu clave y modelos fácilmente.</p>
            </div>
        </div>

        <form id="configForm" onsubmit="saveConfig(event)">
            <div class="form-group">
                <label for="provider">Proveedor de Inteligencia Artificial</label>
                <select id="provider" onchange="updateProviderFields()">
                    {prov_options}
                </select>
            </div>

            <div class="form-group" id="apiKeyGroup">
                <label for="apiKey">API Key / Token de Acceso</label>
                <input type="text" id="apiKey" placeholder="Pega tu API Key aquí (ej. sk-...)" autocomplete="off">
                <div class="helper" id="apiKeyHelper">Tu API Key se guardará cifrada localmente.</div>
            </div>

            <div class="form-group" id="apiBaseGroup">
                <label for="apiBase">Endpoint URL (Base / Proxy)</label>
                <input type="text" id="apiBase" placeholder="https://api.openai.com/v1" autocomplete="off">
                <div class="helper">Opcional: déjalo por defecto o usa un proxy / endpoint personalizado.</div>
            </div>

            <div class="form-group">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                    <label for="model" style="margin-bottom: 0;">Modelo de Inteligencia Artificial</label>
                    <label style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: #00e676; cursor: pointer;">
                        <input type="checkbox" id="filterFree" onchange="renderModelList()" checked style="accent-color: #00e676; cursor: pointer;">
                        <span>🆓 Solo Modelos Gratuitos (Free Tier)</span>
                    </label>
                </div>
                <input type="text" id="model" placeholder="Selecciona o escribe el modelo" autocomplete="off" list="modelList">
                <datalist id="modelList"></datalist>
                <div class="helper" id="modelHelper">Filtrado activo: mostrando modelos sin costo / gratuitos.</div>
            </div>

            <div class="btn-group">
                <button type="submit" class="btn-primary" id="saveBtn">💾 Guardar Configuración y Continuar</button>
            </div>
        </form>

        <div id="statusBox" class="status-box"></div>
    </div>

    <script>
        const providers = {providers_json};
        const currentCfg = {current_config_json};

        function renderModelList() {{
            const p = document.getElementById('provider').value;
            const meta = providers[p] || {{}};
            const onlyFree = document.getElementById('filterFree').checked;

            const allModels = meta.available_models || [];
            const freeModels = meta.free_models || allModels.filter(m => m.toLowerCase().includes(':free') || m.toLowerCase().includes('free'));

            const modelsToDisplay = (onlyFree && freeModels.length > 0) ? freeModels : allModels;

            const dataList = document.getElementById('modelList');
            dataList.innerHTML = '';
            modelsToDisplay.forEach(m => {{
                const opt = document.createElement('option');
                opt.value = m;
                dataList.appendChild(opt);
            }});

            const helper = document.getElementById('modelHelper');
            if (onlyFree && freeModels.length > 0) {{
                helper.innerText = `Mostrando ${{modelsToDisplay.length}} modelos 100% gratuitos para ${{meta.name || p}}.`;
                helper.style.color = '#00e676';
            }} else {{
                helper.innerText = `Mostrando catálogo completo de ${{modelsToDisplay.length}} modelos disponibles.`;
                helper.style.color = 'var(--text-muted)';
            }}

            const modelInput = document.getElementById('model');
            if (!modelsToDisplay.includes(modelInput.value)) {{
                modelInput.value = modelsToDisplay[0] || meta.default_model || '';
            }}
        }}

        function updateProviderFields() {{
            const p = document.getElementById('provider').value;
            const meta = providers[p] || {{}};

            // Actualizar API Key
            const keyInput = document.getElementById('apiKey');
            const keyGroup = document.getElementById('apiKeyGroup');
            if (meta.requires_api_key === false) {{
                keyGroup.style.display = 'none';
            }} else {{
                keyGroup.style.display = 'block';
                keyInput.value = currentCfg.api_keys[p] || '';
            }}

            // Actualizar API Base
            const baseInput = document.getElementById('apiBase');
            baseInput.value = currentCfg.api_bases[p] || meta.default_api_base || '';

            renderModelList();

            const modelInput = document.getElementById('model');
            if (p === currentCfg.active_provider && currentCfg.active_model) {{
                modelInput.value = currentCfg.active_model;
            }}
        }}

        async function saveConfig(e) {{
            e.preventDefault();
            const btn = document.getElementById('saveBtn');
            btn.disabled = true;
            btn.innerText = 'Guardando...';

            const payload = {{
                provider: document.getElementById('provider').value,
                api_key: document.getElementById('apiKey').value.trim(),
                api_base: document.getElementById('apiBase').value.trim(),
                model: document.getElementById('model').value.trim()
            }};

            try {{
                const res = await fetch('/save', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(payload)
                }});
                const data = await res.json();
                if (data.ok) {{
                    const box = document.getElementById('statusBox');
                    box.className = 'status-box success';
                    box.innerText = '✓ ¡Configuración guardada exitosamente! Puedes cerrar esta ventana y regresar a tu terminal.';
                    setTimeout(() => {{
                        window.close();
                    }}, 2000);
                }}
            }} catch (err) {{
                alert('Error al guardar: ' + err.message);
                btn.disabled = false;
                btn.innerText = '💾 Guardar Configuración y Continuar';
            }}
        }}

        updateProviderFields();
    </script>
</body>
</html>"""
                self.wfile.write(html.encode("utf-8"))

            elif self.path == "/close":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK")
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            if self.path == "/save":
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8")
                data = json.loads(body)

                provider = data.get("provider")
                api_key = data.get("api_key", "")
                api_base = data.get("api_base", "")
                model = data.get("model", "")

                if provider:
                    if model:
                        config_mgr.set_provider(provider, model)
                    else:
                        config_mgr.set_provider(provider)

                    if api_key:
                        config_mgr.set_api_key(provider, api_key)

                    if api_base:
                        if "api_bases" not in config_mgr.config:
                            config_mgr.config["api_bases"] = {}
                        config_mgr.config["api_bases"][provider] = api_base
                        config_mgr.save()

                    saved_state["saved"] = True
                    saved_state["provider"] = provider
                    saved_state["model"] = config_mgr.get_active_model()

                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))

    class ThreadingConfigServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True
        allow_reuse_address = True

    server = None
    for p in range(port, port + 10):
        try:
            server = ThreadingConfigServer(("127.0.0.1", p), ConfigHTTPHandler)
            port = p
            break
        except OSError:
            continue

    if not server:
        console.print("[bold red][!] No se pudo iniciar el portal web de configuración en puertos 8999-9009.[/bold red]")
        return False

    url = f"http://127.0.0.1:{port}"
    console.print(f"\n[bold green][✓] Servidor de configuración Web iniciado en:[/bold green] [bold cyan]{url}[/bold cyan]")
    console.print("[dim]Abriendo navegador automáticamente... (Presiona Ctrl+C en la terminal para volver si ya terminaste)[/dim]\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        while not saved_state["saved"]:
            server.handle_request()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            server.server_close()
        except Exception:
            pass

    if saved_state["saved"]:
        console.print(f"[bold green][✓] Configuración guardada vía Web:[/bold green] [bold white]{saved_state['provider']}[/bold white] → [bold yellow]{saved_state['model']}[/bold yellow]")
        return True
    return False


def interactive_config_wizard(config_mgr: ConfigManager) -> bool:
    """Guía al usuario paso a paso en la configuración de Blood-Cipher, con opción CLI o Web."""
    console.print()
    console.print(
        Panel(
            "[bold cyan]Asistente de Configuración de Modelos y Credenciales de IA[/bold cyan]\n"
            "[dim]Puedes configurar todo desde la terminal (CLI) o abrir el configurador visual en tu navegador (Web).[/dim]",
            title="⚙️ CONFIGURACIÓN BLOOD-CIPHER",
            border_style="cyan",
        )
    )

    # Preguntar si prefiere Auto-Detección, Asistente Web o Asistente CLI
    mode_choice = questionary.select(
        "¿Cómo prefieres configurar Blood-Cipher?",
        choices=[
            questionary.Choice(
                title="⚡ [Auto-Detectar por Token/API Key] (Pega tu clave: detecta el proveedor y modelos automáticamente)",
                value="AUTO"
            ),
            questionary.Choice(
                title="🌐 [Configurador Web Visual] (Abre tu navegador, pega tu API Key y elige modelos fácilmente)",
                value="WEB"
            ),
            questionary.Choice(
                title="💻 [Configurador por Terminal / CLI Manual] (Elegir proveedor paso a paso)",
                value="CLI"
            ),
            questionary.Choice(title="🔙 Regresar / Cancelar", value="BACK"),
        ],
        default="AUTO"
    ).ask()

    if not mode_choice or mode_choice == "BACK":
        console.print("[yellow][*] Regresando al menú anterior.[/yellow]")
        return False

    if mode_choice == "AUTO":
        entered_key = questionary.text(
            "Pega tu API Key o Auth Token (ej. sk-bl-..., hf_..., gsk_..., AIzaSy..., sk-...):"
        ).ask()
        if not entered_key or not entered_key.strip():
            console.print("[yellow][*] Operación cancelada.[/yellow]")
            return False

        entered_key = entered_key.strip()
        with console.status("[bold cyan]Analizando firma de clave y consultando servidores de IA en tiempo real...[/bold cyan]", spinner="dots"):
            det_res = detect_provider_and_models(entered_key)

        if not det_res.get("success") or not det_res.get("provider"):
            console.print(f"[yellow][!] {det_res.get('message', 'No se pudo identificar el proveedor automáticamente.')}[/yellow]")
            console.print("[dim]Continuando al asistente manual paso a paso...[/dim]")
        else:
            prov = det_res["provider"]
            prov_name = det_res["name"]
            models = det_res.get("models", [])
            api_base = det_res.get("api_base", "")

            console.print()
            console.print(f"[bold green][✓] ¡Proveedor identificado con éxito![/bold green] [bold white]{prov_name}[/bold white] (`{prov}`)")
            if models:
                console.print(f"[bold green][✓] Se descubrieron {len(models)} modelos disponibles en tu cuenta.[/bold green]")

            # Guardar la API Key y API Base descubierta
            config_mgr.set_api_key(prov, entered_key)
            if api_base:
                if "api_bases" not in config_mgr.config:
                    config_mgr.config["api_bases"] = {}
                config_mgr.config["api_bases"][prov] = api_base
                config_mgr.save()

            # Selección de modelo: ofrecer enrutamiento gratuito
            free_prov_models = config_mgr.get_free_models(prov)
            all_discovered = list(models) if models else list(DEFAULT_PROVIDERS.get(prov, {}).get("available_models", []))
            
            # Si se descubrieron modelos en vivo y hay modelos gratuitos conocidos
            discovered_free = [m for m in all_discovered if any(f.split('/')[-1] == m.split('/')[-1] for f in free_prov_models) or ":free" in m.lower() or "free" in m.lower()]
            if not discovered_free and free_prov_models:
                discovered_free = list(free_prov_models)

            filter_mode = "ALL"
            if discovered_free:
                ask_routing = questionary.select(
                    "¿Qué tipo de enrutamiento deseas activar para este proveedor?",
                    choices=[
                        questionary.Choice(
                            title=f"🆓 [Enrutamiento Gratuito / Solo Modelos Free] ({len(discovered_free)} modelos sin costo)",
                            value="FREE"
                        ),
                        questionary.Choice(
                            title=f"🌐 [Ver Todos los Modelos Disponibles] ({len(all_discovered)} modelos)",
                            value="ALL"
                        ),
                    ],
                    default="FREE"
                ).ask()
                if ask_routing:
                    filter_mode = ask_routing

            if filter_mode == "FREE" and discovered_free:
                model_choices = list(discovered_free)
                console.print(f"[bold green][✓] Filtrando solo modelos 100% gratuitos para {prov_name}.[/bold green]")
            else:
                model_choices = list(all_discovered)

            if not model_choices:
                model_choices = [det_res.get("default_model") or "deepseek-v3.2"]

            model_choices.append("Personalizado (Escribir manualmente)")
            model_choices.append("🔙 Cancelar")

            def_mod = model_choices[0]
            if det_res.get("default_model") in model_choices:
                def_mod = det_res.get("default_model")

            chosen_m = questionary.select(
                f"Selecciona el modelo activo para {prov_name}:",
                choices=model_choices,
                default=def_mod
            ).ask()

            if not chosen_m or chosen_m.startswith("🔙"):
                return False

            if chosen_m.startswith("Personalizado"):
                manual_m = questionary.text("Ingresa el identificador del modelo:").ask()
                if manual_m and manual_m.strip():
                    chosen_m = manual_m.strip()
                else:
                    chosen_m = def_mod

            config_mgr.set_provider(prov, chosen_m)
            console.print(f"[bold green][✓] ¡Configuración completada y activa![/bold green] [cyan]{prov.upper()}[/cyan] → [yellow]{chosen_m}[/yellow]")

            test_now = questionary.confirm("¿Deseas realizar un test de conexión ahora?", default=True).ask()
            if test_now:
                test_provider_connection(config_mgr)
            return True

    if mode_choice == "WEB":
        return _run_web_config_portal(config_mgr)

    # 1. Selección de Proveedor CLI
    provider_choices = [
        questionary.Choice(
            title=f"{info['name']} ({prov})",
            value=prov
        )
        for prov, info in DEFAULT_PROVIDERS.items()
    ]
    provider_choices.append(questionary.Choice(title="🔙 Regresar / Cancelar", value="BACK"))

    current_provider = config_mgr.get_active_provider()
    default_choice = next((c for c in provider_choices if c.value == current_provider), provider_choices[0])

    try:
        chosen_provider = questionary.select(
            "Elige tu proveedor de Inteligencia Artificial:",
            choices=provider_choices,
            default=default_choice,
        ).ask()
    except (KeyboardInterrupt, EOFError):
        console.print("[yellow]\n[*] Configuración cancelada. Regresando...[/yellow]")
        return False

    if not chosen_provider or chosen_provider == "BACK":
        console.print("[yellow][*] Regresando al menú anterior.[/yellow]")
        return False

    prov_meta = DEFAULT_PROVIDERS[chosen_provider]

    # 2. Solicitar API Key o Endpoint URL PRIMERO
    api_key = ""
    api_base = None

    try:
        if prov_meta.get("requires_api_key", True):
            current_key = config_mgr.get_api_key(chosen_provider)
            key_count = config_mgr.get_api_key_count(chosen_provider)
            key_hint = f" (Actual: {'*'*6}...{current_key[-4:]})" if current_key and len(current_key) > 8 else ""
            if key_count > 1:
                key_hint += f" [{key_count} keys en pool]"

            entered_key = questionary.text(
                f"Ingresa tu API Key para {prov_meta['name']}{key_hint} (o presiona Enter para conservar):"
            ).ask()

            if entered_key is None:
                console.print("[yellow]\n[*] Operación cancelada. Regresando...[/yellow]")
                return False

            if entered_key and entered_key.strip():
                api_key = entered_key.strip()
                config_mgr.set_api_key(chosen_provider, api_key)
            else:
                api_key = current_key or ""

            if not api_key:
                console.print("[yellow][!] Advertencia: No se proporcionó API Key para este proveedor.[/yellow]")

            # Ofrecer configurar múltiples keys para rotación automática
            if api_key:
                add_more = questionary.confirm(
                    f"¿Deseas agregar más API Keys de {prov_meta['name']} para rotación automática? (evita rate limits)",
                    default=False
                ).ask()
                if add_more:
                    all_keys = [api_key]
                    console.print("[dim]Pega cada API Key adicional (una por línea). Escribe 'FIN' para terminar:[/dim]")
                    while True:
                        extra_key = questionary.text("API Key adicional (o 'FIN'):").ask()
                        if not extra_key or extra_key.strip().upper() == "FIN":
                            break
                        if extra_key.strip():
                            all_keys.append(extra_key.strip())
                            console.print(f"[green]  ✓ Key #{len(all_keys)} agregada[/green]")
                    if len(all_keys) > 1:
                        config_mgr.set_api_keys(chosen_provider, all_keys)
                        console.print(f"[bold green][✓] {len(all_keys)} API Keys configuradas para rotación automática en {prov_meta['name']}[/bold green]")
            if "default_api_base" in prov_meta:
                current_base = config_mgr.get_api_base(chosen_provider) or prov_meta["default_api_base"]
                api_base_input = questionary.text(
                    f"Endpoint URL (Base) para {prov_meta['name']}:",
                    default=current_base,
                ).ask()
                if api_base_input is None:
                    return False
                if api_base_input:
                    api_base = api_base_input.strip().rstrip("/")
                    if api_base.endswith("/chat/completions"):
                        api_base = api_base[:-len("/chat/completions")].rstrip("/")
                    if "api_bases" not in config_mgr.config:
                        config_mgr.config["api_bases"] = {}
                    config_mgr.config["api_bases"][chosen_provider] = api_base
            else:
                api_base = config_mgr.get_api_base(chosen_provider)
        else:
            # Proveedor sin API Key (como Ollama)
            current_base = config_mgr.get_api_base(chosen_provider) or prov_meta.get("default_api_base", "http://localhost:11434")
            api_base_input = questionary.text(
                f"Endpoint URL de {prov_meta['name']}:",
                default=current_base,
            ).ask()
            if api_base_input is None:
                return False
            if api_base_input:
                base_clean = api_base_input.strip().rstrip("/")
                if base_clean.endswith("/chat/completions"):
                    base_clean = base_clean[:-len("/chat/completions")].rstrip("/")
                if "api_bases" not in config_mgr.config:
                    config_mgr.config["api_bases"] = {}
                config_mgr.config["api_bases"][chosen_provider] = base_clean
                api_base = base_clean

        # 3. Consultar modelos activos en vivo desde la API del proveedor
        live_models = []
        with console.status(f"[bold cyan]Consultando modelos activos en tiempo real para {prov_meta['name']}...[/bold cyan]", spinner="dots"):
            live_models = fetch_live_models(chosen_provider, api_key=api_key, api_base=api_base)

        all_detected = live_models if live_models else list(prov_meta.get("available_models", []))
        free_models = config_mgr.get_free_models(chosen_provider)

        # Para Ollama todos los modelos locales son 100% gratuitos y offline
        if chosen_provider == "ollama":
            filter_mode = "ALL"
            model_choices = list(all_detected)
        elif free_models:
            free_choice = questionary.select(
                "¿Qué tipo de enrutamiento deseas utilizar?",
                choices=[
                    questionary.Choice(
                        title=f"🆓 [Solo Modelos Gratuitos / Free Routing] ({len(free_models)} modelos sin costo)",
                        value="FREE"
                    ),
                    questionary.Choice(
                        title=f"🌐 [Ver Todos los Modelos Disponibles] ({len(all_detected)} modelos en catálogo)",
                        value="ALL"
                    ),
                ],
                default="FREE"
            ).ask()
            if free_choice:
                filter_mode = free_choice

            if filter_mode == "FREE":
                model_choices = list(free_models)
                console.print(f"[bold green][✓] Enrutamiento gratuito activado: Mostrando {len(model_choices)} modelos sin costo para {prov_meta['name']}.[/bold green]")
            else:
                model_choices = list(all_detected)
                if live_models:
                    console.print(f"[bold green][✓] Se detectaron {len(live_models)} modelos activos disponibles en tu cuenta.[/bold green]")
        else:
            model_choices = list(all_detected)


        model_choices.append("Personalizado (Escribir manualmente)")
        model_choices.append("🔙 Cancelar y Regresar")

        current_model = config_mgr.get_active_model()
        default_model = current_model if current_model in model_choices else model_choices[0]

        # 4. Selección del modelo activo
        chosen_model = questionary.select(
            f"Elige el modelo para {prov_meta['name']}:",
            choices=model_choices,
            default=default_model,
        ).ask()

        if not chosen_model or chosen_model.startswith("🔙"):
            console.print("[yellow][*] Selección de modelo cancelada. Regresando...[/yellow]")
            return False

        if chosen_model.startswith("Personalizado"):
            custom_model = questionary.text(
                "Ingresa el identificador exacto del modelo (ej. openai/deepseek-chat, groq/llama-3.3-70b-versatile):",
                default=prov_meta["default_model"],
            ).ask()
            if custom_model:
                chosen_model = custom_model.strip()
                # Asegurar prefijo compatible con litellm si el usuario no puso '/'
                if "/" not in chosen_model:
                    if chosen_provider in ["bai", "aimlapi"]:
                        chosen_model = f"openai/{chosen_model}"
                    elif chosen_provider == "groq":
                        chosen_model = f"groq/{chosen_model}"
                    elif chosen_provider == "openrouter":
                        chosen_model = f"openrouter/{chosen_model}"
                    elif chosen_provider == "ollama":
                        chosen_model = f"ollama/{chosen_model}"
                    elif chosen_provider == "gemini":
                        chosen_model = f"gemini/{chosen_model}"
            else:
                chosen_model = prov_meta["default_model"]

        # Guardar proveedor y modelo
        config_mgr.set_provider(chosen_provider, chosen_model)

        console.print()
        console.print("[bold green][✓] ¡Configuración guardada correctamente en ~/.config/blood-cipher/config.json![/bold green]")
        console.print(f"[cyan]Proveedor activo:[/cyan] {chosen_provider.upper()} | [yellow]Modelo:[/yellow] {chosen_model}")

        # Probar conexión opcionalmente
        test_now = questionary.confirm("¿Deseas realizar un test de conexión ahora?", default=True).ask()
        if test_now:
            test_provider_connection(config_mgr)

        return True
    except (KeyboardInterrupt, EOFError):
        console.print("[yellow]\n[*] Configuración interrumpida. Regresando al menú principal...[/yellow]")
        return False

    return True


def test_provider_connection(config_mgr: ConfigManager) -> bool:
    """Prueba la conexión con el modelo configurado mediante el driver independiente del proveedor."""
    from coder_kali.providers.factory import get_provider

    provider_name = config_mgr.get_active_provider()
    model = config_mgr.get_active_model()

    console.print()
    with console.status(f"[bold cyan]Probando comunicación con {model} ({provider_name.upper()})...[/bold cyan]", spinner="dots"):
        try:
            driver = get_provider(provider_name, config_mgr)
            success, msg = driver.test_connection(model)
            if success:
                console.print(f"[bold green][✓] {msg}[/bold green]")
                return True
            else:
                console.print(f"[bold red][✗] Falló la prueba de conexión:[/bold red] {msg}")
                console.print("[dim]Verifica tu API Key, saldo disponible o selecciona otro modelo.[/dim]")
                return False
        except Exception as e:
            console.print(f"[bold red][✗] Error inesperado en la prueba:[/bold red] {str(e)}")
            return False
