"""
coder_kali/providers/openrouter.py - Driver independiente para OpenRouter.
"""

from typing import Any, Dict, List, Tuple
import requests

from .base import BaseLLMProvider, LLMResponse


class OpenRouterProvider(BaseLLMProvider):
    """Driver dedicado para OpenRouter (Acceso universal a 200+ modelos)."""

    API_URL = "https://openrouter.ai/api/v1/chat/completions"

    def _clean_model_name(self, model: str) -> str:
        if not model:
            return "deepseek/deepseek-r1"
        m = model.strip()
        if m.lower().startswith("openrouter/"):
            m = m[len("openrouter/"):]
        return m

    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs,
    ) -> LLMResponse:
        clean_model = self._clean_model_name(model)
        api_key = self.config_mgr.get_api_key("openrouter")
        if not api_key:
            return LLMResponse(
                error="No hay API Key configurada para OpenRouter. Ejecuta 'blood-cipher config'.",
                success=False,
            )

        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "HTTP-Referer": "https://github.com/Sammir1209/coder-kali",
            "X-Title": "Blood-Cipher",
            "Content-Type": "application/json",
        }
        payload = {
            "model": clean_model,
            "messages": messages,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
        }

        try:
            current_max_tokens = int(max_tokens)
            resp = requests.post(self.API_URL, json=payload, headers=headers, timeout=120)
            if resp.status_code == 402:
                # OpenRouter error 402: "This request requires more credits, or fewer max_tokens. You requested up to 4096 tokens, but can only afford 2097..."
                import re
                err_text = resp.text
                match = re.search(r"can only afford\s+(\d+)", err_text, re.IGNORECASE)
                if match:
                    affordable = int(match.group(1))
                    if affordable > 100:
                        payload["max_tokens"] = affordable - 20
                        resp = requests.post(self.API_URL, json=payload, headers=headers, timeout=120)

            if resp.status_code != 200:
                err_text = resp.text
                if resp.status_code == 401:
                    return LLMResponse(
                        error="API Key de OpenRouter inválida o sin créditos. Revisa tu cuenta en https://openrouter.ai/.",
                        success=False,
                    )
                if resp.status_code == 402:
                    return LLMResponse(
                        error="Créditos insuficientes en OpenRouter para este modelo de pago. Puedes recargar en https://openrouter.ai/settings/credits o cambiar a un modelo gratuito como 'deepseek/deepseek-chat:free' o 'google/gemini-2.0-flash-exp:free'.",
                        success=False,
                    )
                if resp.status_code == 429:
                    return LLMResponse(error="Rate limit excedido en OpenRouter.", success=False)
                return LLMResponse(error=f"Error en OpenRouter ({resp.status_code}): {err_text}", success=False)

            data = resp.json()
            choice = data.get("choices", [{}])[0]
            msg_obj = choice.get("message", {})
            content = msg_obj.get("content", "") or ""
            reasoning = msg_obj.get("reasoning", "") or ""
            usage = data.get("usage", {}).get("total_tokens", 0)

            return LLMResponse(
                content=content,
                reasoning_content=reasoning,
                raw_response=data,
                tokens_used=usage,
                success=True,
            )
        except requests.exceptions.Timeout:
            return LLMResponse(error="Timeout de conexión con OpenRouter.", success=False)
        except Exception as e:
            return LLMResponse(error=f"Excepción en OpenRouter: {str(e)}", success=False)

    def test_connection(self, model: str) -> Tuple[bool, str]:
        clean_model = self._clean_model_name(model)
        test_messages = [{"role": "user", "content": "Responde únicamente 'OK'"}]
        res = self.chat_completion(clean_model, test_messages, max_tokens=15)
        if res.success:
            return True, f"Conexión exitosa con OpenRouter ({clean_model}): {res.content.strip() or 'OK'}"
        return False, res.error or "Error al conectar con OpenRouter"
