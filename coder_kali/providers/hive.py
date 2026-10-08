"""
coder_kali/providers/hive.py - Driver dedicado para Hive AI (thehive.ai).
Soporta endpoints OpenAI-compatible en https://api.thehive.ai/api/v3 y clusters regionales (sf1, va1).
Permite autenticación con Service API Key / Statement Policy Permissions (hive:CallApi).
"""

import json
from typing import Any, Dict, List, Optional, Tuple
import requests

from .base import BaseLLMProvider, LLMResponse


class HiveProvider(BaseLLMProvider):
    """Driver dedicado para Hive AI (thehive.ai API v3)."""

    DEFAULT_BASE = "https://api.thehive.ai/api/v3"

    def _clean_model_name(self, model: str) -> str:
        """Limpia prefijos innecesarios conservando el id exacto del modelo de Hive."""
        if not model:
            return "deepseek-ai/deepseek-v4.1-flash"
        m = model.strip()
        for prefix in ("hive/", "hive:models:", "thehive/"):
            if m.lower().startswith(prefix):
                m = m[len(prefix):]
        return m

    def _get_api_base(self) -> str:
        base = self.config_mgr.get_api_base("hive") or self.DEFAULT_BASE
        base = base.strip().rstrip("/")
        if base.endswith("/chat/completions"):
            base = base[:-len("/chat/completions")].rstrip("/")
        return base

    def _parse_hive_error(self, status_code: int, error_text: str, model: str) -> str:
        err_lower = error_text.lower()
        if "statement" in err_lower or "permission" in err_lower or "forbidden" in err_lower or status_code == 403:
            return (
                f"Error de Permisos en Hive AI (403): Tu API Key no tiene permiso 'hive:CallApi' "
                f"para el recurso o cluster del modelo '{model}'. "
                "Verifica el statement en tu política: hive:models:sf1:::v3/* o hive:models:va1:::v3/*."
            )
        if status_code == 401 or "unauthorized" in err_lower or "invalid api key" in err_lower:
            return (
                "Error de Autenticación en Hive AI (401): API Key no autorizada o revocada. "
                "Genera una nueva en https://docs.thehive.ai/docs/token-permissions y actualízala con 'blood-cipher config'."
            )
        if status_code == 429 or "rate limit" in err_lower:
            return "Límite de peticiones alcanzado en Hive AI (429 Rate Limit). Aguarda un momento o rota tu clave."
        return f"Error en Hive AI (HTTP {status_code}): {error_text}"

    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs,
    ) -> LLMResponse:
        clean_model = self._clean_model_name(model)
        api_base = self._get_api_base()
        endpoint = f"{api_base}/chat/completions"

        api_key = self.config_mgr.get_api_key("hive")
        if not api_key:
            return LLMResponse(
                error=(
                    "No hay API Key configurada para Hive AI. "
                    "Obtén tu clave en https://docs.thehive.ai/ y configúrala con 'blood-cipher config'."
                ),
                success=False,
            )

        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
            "User-Agent": "Blood-Cipher/2.0 (Hive-Cluster-Driver)",
        }

        payload = {
            "model": clean_model,
            "messages": messages,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
        }

        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=120)

            # Rotación en 429 si hay más llaves en el pool
            if resp.status_code == 429:
                next_key = self.config_mgr.rotate_api_key("hive")
                if next_key and next_key != api_key:
                    headers["Authorization"] = f"Bearer {next_key.strip()}"
                    resp = requests.post(endpoint, json=payload, headers=headers, timeout=120)

            if resp.status_code != 200:
                err_text = self._parse_hive_error(resp.status_code, resp.text, clean_model)
                return LLMResponse(error=err_text, success=False)

            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                return LLMResponse(
                    content="",
                    raw_response=data,
                    success=False,
                    error="Respuesta vacía recibida desde Hive AI API.",
                )

            choice = choices[0]
            msg_obj = choice.get("message", {})
            content = msg_obj.get("content", "") or ""
            reasoning = msg_obj.get("reasoning_content", "") or msg_obj.get("reasoning", "") or ""
            usage = data.get("usage", {}).get("total_tokens", 0)

            return LLMResponse(
                content=content,
                reasoning_content=reasoning,
                raw_response=data,
                tokens_used=usage,
                success=True,
            )

        except requests.exceptions.Timeout:
            return LLMResponse(error="Timeout de conexión con Hive AI API (120s excedidos).", success=False)
        except requests.exceptions.ConnectionError:
            return LLMResponse(
                error=f"No se pudo conectar con el endpoint de Hive AI en {endpoint}. Revisa tu conexión o VPN.",
                success=False,
            )
        except Exception as e:
            return LLMResponse(error=f"Excepción en Hive AI Provider: {str(e)}", success=False)

    def test_connection(self, model: str) -> Tuple[bool, str]:
        clean_model = self._clean_model_name(model)
        test_messages = [{"role": "user", "content": "Responde únicamente 'OK'"}]
        res = self.chat_completion(clean_model, test_messages, max_tokens=20)
        if res.success:
            return True, f"Conexión exitosa con Hive AI ({clean_model}): {res.content.strip() or 'OK'}"
        return False, res.error or "Error desconocido al conectar con Hive AI"
