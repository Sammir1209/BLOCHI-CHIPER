"""
coder_kali/providers/plugsky.py - Driver dedicado para Plugsky AI (plugsky.com).
Comunica directamente vía HTTP REST OpenAI-compatible contra https://api.plugsky.com/v1.
"""

import json
from typing import Any, Dict, List, Optional, Tuple
import requests

from .base import BaseLLMProvider, LLMResponse


class PlugskyProvider(BaseLLMProvider):
    """Driver dedicado para Plugsky AI (plugsky.com - One OpenAI-compatible API for 30+ models)."""

    DEFAULT_BASE = "https://api.plugsky.com/v1"

    def _clean_model_name(self, model: str) -> str:
        """Limpia prefijos innecesarios conservando el id exacto del modelo."""
        if not model:
            return "plugsky-pro"
        m = model.strip()
        for prefix in ("plugsky/", "plug/"):
            if m.lower().startswith(prefix):
                m = m[len(prefix):]
        return m

    def _get_api_base(self) -> str:
        base = self.config_mgr.get_api_base("plugsky") or self.DEFAULT_BASE
        base = base.strip().rstrip("/")
        if base.endswith("/chat/completions"):
            base = base[:-len("/chat/completions")].rstrip("/")
        return base

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

        api_key = self.config_mgr.get_api_key("plugsky")
        if not api_key:
            return LLMResponse(
                error=(
                    "No hay API Key configurada para Plugsky. "
                    "Obtén tu clave en https://plugsky.com/dashboard#keys y configúrala con 'blood-cipher config'."
                ),
                success=False,
            )

        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (Blood-Cipher/2.0)",
        }

        payload = {
            "model": clean_model,
            "messages": messages,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
        }

        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=120)

            # Manejo de rotación en caso de rate limit
            if resp.status_code == 429:
                next_key = self.config_mgr.rotate_api_key("plugsky")
                if next_key and next_key != api_key:
                    headers["Authorization"] = f"Bearer {next_key.strip()}"
                    resp = requests.post(endpoint, json=payload, headers=headers, timeout=120)

            if resp.status_code != 200:
                err_text = resp.text
                if resp.status_code == 401 or resp.status_code == 403:
                    return LLMResponse(
                        error=(
                            f"Acceso denegado en Plugsky (HTTP {resp.status_code}). "
                            "Verifica tu API Key en https://plugsky.com/dashboard#keys."
                        ),
                        success=False,
                    )
                if resp.status_code == 402 or "insufficient credits" in err_text.lower():
                    return LLMResponse(
                        error=(
                            "Créditos o cuota insuficiente en Plugsky (HTTP 402). "
                            "Revisa tu suscripción en https://plugsky.com/dashboard."
                        ),
                        success=False,
                    )
                if resp.status_code == 429:
                    return LLMResponse(
                        error="Límite de peticiones alcanzado en Plugsky (429 Rate Limit). Intenta más tarde o rota tu API Key.",
                        success=False,
                    )
                return LLMResponse(
                    error=f"Error en Plugsky ({resp.status_code}): {err_text}",
                    success=False,
                )

            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                return LLMResponse(
                    content="",
                    raw_response=data,
                    success=False,
                    error="Respuesta vacía recibida desde Plugsky API.",
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
            return LLMResponse(error="Timeout de conexión con Plugsky API (120s excedidos).", success=False)
        except Exception as e:
            return LLMResponse(error=f"Excepción en Plugsky Provider: {str(e)}", success=False)

    def test_connection(self, model: str) -> Tuple[bool, str]:
        clean_model = self._clean_model_name(model)
        test_messages = [{"role": "user", "content": "Responde únicamente 'OK'"}]
        res = self.chat_completion(clean_model, test_messages, max_tokens=20)
        if res.success:
            return True, f"Conexión exitosa con Plugsky ({clean_model}): {res.content.strip() or 'OK'}"
        return False, res.error or "Error desconocido al conectar con Plugsky"
