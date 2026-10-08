"""
coder_kali/providers/ollama.py - Driver nativo ultrarrápido para Ollama Local.
"""

from typing import Any, Dict, List, Tuple
from coder_kali.fast_engine import OllamaFastClient
from .base import BaseLLMProvider, LLMResponse


class OllamaProvider(BaseLLMProvider):
    """Driver nativo para Ollama en local o red privada."""

    def _get_client(self) -> OllamaFastClient:
        host = self.config_mgr.get_api_base("ollama") or "http://localhost:11434"
        return OllamaFastClient(host=host)

    def _clean_model_name(self, model: str) -> str:
        if not model:
            return "qwen2.5-coder:1.5b"
        m = model.strip()
        if m.lower().startswith("ollama/"):
            m = m[len("ollama/"):]
        return m

    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs,
    ) -> LLMResponse:
        client = self._get_client()
        clean_model = self._clean_model_name(model)

        if not client.is_online():
            return LLMResponse(
                error=f"El servicio de Ollama no está activo en {client.host}. Inícialo con 'ollama serve'.",
                success=False,
            )

        res = client.chat_completion(
            model=clean_model,
            messages=messages,
            temperature=temperature,
            timeout=300,
        )

        if "error" in res:
            return LLMResponse(error=f"Error en Ollama: {res['error']}", success=False)

        return LLMResponse(
            content=res.get("content", ""),
            raw_response=res,
            tokens_used=res.get("eval_count", 0),
            success=True,
        )

    def test_connection(self, model: str) -> Tuple[bool, str]:
        client = self._get_client()
        clean_model = self._clean_model_name(model)

        if not client.is_online():
            return False, f"El servicio de Ollama no está activo en {client.host}."

        test_messages = [{"role": "user", "content": "Responde únicamente 'OK'"}]
        res = self.chat_completion(clean_model, test_messages, max_tokens=15)
        if res.success:
            return True, f"Conexión exitosa con Ollama ({clean_model}): {res.content.strip() or 'OK'}"
        return False, res.error or "Error al conectar con Ollama"

    def list_models(self) -> List[str]:
        client = self._get_client()
        return client.list_local_models()
