"""
coder_kali/fast_engine.py - Motor de Alto Rendimiento para Blood-Cipher.
Integra:
1. orjson: Serialización y deserialización JSON de ultra alta velocidad (Rust).
2. uvloop / asyncio: Event loop optimizado en C para Linux y operaciones concurrentes.
3. OllamaFastClient: Conector directo y ligero a la API de Ollama (http://localhost:11434).
"""

import sys
import os
from typing import Any, Dict, List, Optional, Generator

# ==============================================================================
# 1. ORJSON SPEED LAYER
# ==============================================================================
try:
    import orjson

    def fast_json_dumps(obj: Any, indent: bool = False) -> str:
        """Serializa objetos Python a JSON usando orjson (Rust) a máxima velocidad."""
        opt = orjson.OPT_INDENT_2 if indent else 0
        return orjson.dumps(obj, option=opt).decode("utf-8")

    def fast_json_loads(data: Any) -> Any:
        """Deserializa JSON usando orjson (Rust)."""
        if isinstance(data, (bytes, bytearray)):
            return orjson.loads(data)
        elif isinstance(data, str):
            return orjson.loads(data.encode("utf-8"))
        return data

    HAS_ORJSON = True
except ImportError:
    import json

    def fast_json_dumps(obj: Any, indent: bool = False) -> str:
        """Fallback a json estándar si orjson no está disponible."""
        return json.dumps(obj, indent=2 if indent else None, ensure_ascii=False)

    def fast_json_loads(data: Any) -> Any:
        """Fallback a json estándar si orjson no está disponible."""
        if isinstance(data, (bytes, bytearray)):
            return json.loads(data.decode("utf-8"))
        return json.loads(data)

    HAS_ORJSON = False


# ==============================================================================
# 2. UVLOOP / ASYNCIO ACCELERATOR
# ==============================================================================
def enable_fast_event_loop():
    """Activa uvloop en sistemas POSIX (Linux/macOS) para máxima velocidad de I/O."""
    if sys.platform != "win32":
        try:
            import uvloop
            import asyncio
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            return True
        except ImportError:
            pass
    return False


# ==============================================================================
# 3. OLLAMA FAST INFERENCE CONNECTOR (C++ ENGINE COMMUNICATOR)
# ==============================================================================
class OllamaFastClient:
    """Cliente HTTP ligero para comunicación directa con el motor Ollama en localhost:11434."""

    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host.rstrip("/")

    def is_online(self) -> bool:
        """Comprueba si el demonio ollama serve está activo en segundo plano."""
        import requests
        try:
            res = requests.get(f"{self.host}/api/tags", timeout=2.0)
            return res.status_code == 200
        except Exception:
            return False

    def list_local_models(self) -> List[str]:
        """Obtiene la lista de modelos descargados y creados en Ollama."""
        import requests
        try:
            res = requests.get(f"{self.host}/api/tags", timeout=3.0)
            if res.status_code == 200:
                data = fast_json_loads(res.content)
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []

    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        stream: bool = False,
        timeout: int = 120,
        max_tokens: int = 700,
    ) -> Dict[str, Any]:
        """Envía una petición de chat directamente a Ollama para respuesta ultrarrápida."""
        import requests

        clean_model = model.replace("ollama/", "")
        num_predict = min(max_tokens, 1024) if max_tokens else 700
        payload = {
            "model": clean_model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_ctx": 4096,
                "num_predict": num_predict,
            }
        }



        body = fast_json_dumps(payload)
        headers = {
            "Content-Type": "application/json",
            "Bypass-Tunnel-Reminder": "true",
            "bypass-tunnel-reminder": "1",
            "User-Agent": "BloodCipher/1.5",
        }

        try:
            res = requests.post(
                f"{self.host}/api/chat",
                data=body.encode("utf-8"),
                headers=headers,
                timeout=timeout,
            )
            if res.status_code == 200:
                data = fast_json_loads(res.content)
                if not isinstance(data, dict):
                    return {"error": f"Respuesta no JSON de la API: {res.text[:200]}"}
                return {
                    "content": data.get("message", {}).get("content", ""),
                    "model": data.get("model", clean_model),
                    "total_duration": data.get("total_duration", 0),
                    "eval_count": data.get("eval_count", 0),
                    "eval_duration": data.get("eval_duration", 0),
                }
            else:
                return {"error": f"Error de Ollama HTTP {res.status_code}: {res.text}"}
        except Exception as e:
            return {"error": f"Error de conexión con Ollama: {e}"}

    def chat_stream(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 700,
    ) -> Generator[str, None, None]:
        """Generador de streaming token por token directamente desde Ollama."""
        import requests

        clean_model = model.replace("ollama/", "")
        num_predict = min(max_tokens, 1024) if max_tokens else 700
        payload = {
            "model": clean_model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_ctx": 4096,
                "num_predict": num_predict,
            }
        }

        body = fast_json_dumps(payload)
        headers = {"Content-Type": "application/json"}

        try:
            with requests.post(
                f"{self.host}/api/chat",
                data=body.encode("utf-8"),
                headers=headers,
                stream=True,
                timeout=120,
            ) as res:
                for line in res.iter_lines():
                    if line:
                        chunk = fast_json_loads(line)
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield content
        except Exception as e:
            yield f"\n[!] Error de streaming con Ollama: {e}"
