"""
coder_kali/providers/gemini.py - Driver independiente para Google Gemini (Google AI Studio).
Comunica directamente vía Google Generative Language REST API.
"""

from typing import Any, Dict, List, Optional, Tuple
import requests

from .base import BaseLLMProvider, LLMResponse


class GeminiProvider(BaseLLMProvider):
    """Driver dedicado para Google Gemini."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def _clean_model_name(self, model: str) -> str:
        if not model:
            return "gemini-2.0-flash"
        m = model.strip()
        if m.lower().startswith("gemini/"):
            m = m[len("gemini/"):]
        # Los nombres válidos oficiales en la REST API de Google son: gemini-2.0-flash, gemini-1.5-flash, gemini-1.5-pro.
        # Nombres como 2.5-flash o 3.6-flash no existen en la API y provocan error 503 / Timeout.
        valid_models = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-lite", "gemini-2.0-pro-exp-02-05"]
        if m not in valid_models:
            return "gemini-2.0-flash"
        return m

    def _format_messages(self, messages: List[Dict[str, str]]) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        system_instruction = None
        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = {"parts": [{"text": content}]}
            else:
                gemini_role = "model" if role in ("assistant", "model") else "user"
                contents.append({
                    "role": gemini_role,
                    "parts": [{"text": content}]
                })
        return system_instruction, contents

    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs,
    ) -> LLMResponse:
        clean_model = self._clean_model_name(model)
        api_key = self.config_mgr.get_api_key("gemini")
        if not api_key:
            return LLMResponse(
                error="No hay API Key configurada para Google Gemini. Ejecuta 'blood-cipher config'.",
                success=False,
            )

        url = f"{self.BASE_URL}/{clean_model}:generateContent?key={api_key.strip()}"
        system_instruction, contents = self._format_messages(messages)

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": float(temperature),
                "maxOutputTokens": int(max_tokens),
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_NONE"},
            ]
        }
        if system_instruction:
            payload["system_instruction"] = system_instruction

        try:
            resp = requests.post(url, json=payload, timeout=45)
            
            if resp.status_code == 429:
                next_key = self.config_mgr.rotate_api_key("gemini")
                if next_key and next_key != api_key:
                    url = f"{self.BASE_URL}/{clean_model}:generateContent?key={next_key.strip()}"
                    resp = requests.post(url, json=payload, timeout=90)

            if resp.status_code in [503, 502, 504] or "UNAVAILABLE" in resp.text or "capacity" in resp.text.lower():
                fallback_models = ["gemini-2.0-flash", "gemini-1.5-flash"]
                for fb in fallback_models:
                    if fb != clean_model:
                        fb_url = f"{self.BASE_URL}/{fb}:generateContent?key={api_key.strip()}"
                        try:
                            fb_resp = requests.post(fb_url, json=payload, timeout=30)
                            if fb_resp.status_code == 200:
                                data = fb_resp.json()
                                candidates = data.get("candidates", [])
                                if candidates:
                                    first = candidates[0]
                                    parts = first.get("content", {}).get("parts", [])
                                    content_text = "".join(part.get("text", "") for part in parts)
                                    return LLMResponse(
                                        content=content_text,
                                        raw_response=data,
                                        success=True,
                                    )
                        except Exception:
                            continue

            if resp.status_code != 200:
                err_text = resp.text
                if resp.status_code == 400:
                    return LLMResponse(
                        error=f"Petición inválida a Gemini (HTTP 400). Verifica que el modelo '{clean_model}' esté disponible.",
                        success=False,
                    )
                if resp.status_code == 403:
                    return LLMResponse(
                        error="API Key de Google Gemini inválida o sin permisos (HTTP 403). Obtén una en https://aistudio.google.com/.",
                        success=False,
                    )
                if resp.status_code == 429:
                    return LLMResponse(
                        error="Cuota de Google Gemini alcanzada (429 Rate Limit).",
                        success=False,
                    )
                return LLMResponse(error=f"Error en Gemini ({resp.status_code}): {err_text}", success=False)

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return LLMResponse(content="", raw_response=data, success=True)

            first = candidates[0]
            parts = first.get("content", {}).get("parts", [])
            content_text = "".join(part.get("text", "") for part in parts)
            usage = data.get("usageMetadata", {}).get("totalTokenCount", 0)

            return LLMResponse(
                content=content_text,
                raw_response=data,
                tokens_used=usage,
                success=True,
            )

        except requests.exceptions.Timeout:
            return LLMResponse(error="Timeout de conexión con Google Gemini.", success=False)
        except Exception as e:
            return LLMResponse(error=f"Excepción en Gemini: {str(e)}", success=False)

    def test_connection(self, model: str) -> Tuple[bool, str]:
        clean_model = self._clean_model_name(model)
        test_messages = [{"role": "user", "content": "Responde únicamente 'OK'"}]
        res = self.chat_completion(clean_model, test_messages, max_tokens=20)
        if res.success:
            return True, f"Conexión exitosa con Gemini ({clean_model}): {res.content.strip() or 'OK'}"
        return False, res.error or "Error al conectar con Gemini"
