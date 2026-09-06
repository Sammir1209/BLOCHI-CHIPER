"""
coder_kali/providers/factory.py - Factoría y registro dinámico de proveedores de IA.
"""

from typing import Any, Dict, Type
from .base import BaseLLMProvider
from .bai import BaiChatProvider
from .gemini import GeminiProvider
from .groq import GroqProvider
from .ollama import OllamaProvider
from .aimlapi import AimlApiProvider
from .openrouter import OpenRouterProvider
from .puter import PuterProvider
from .bazaarlink import BazaarLinkProvider
from .plugsky import PlugskyProvider
from .fallback import GenericLLMProvider

PROVIDER_REGISTRY: Dict[str, Type[BaseLLMProvider]] = {
    "bai": BaiChatProvider,
    "gemini": GeminiProvider,
    "groq": GroqProvider,
    "ollama": OllamaProvider,
    "aimlapi": AimlApiProvider,
    "openrouter": OpenRouterProvider,
    "puter": PuterProvider,
    "bazaarlink": BazaarLinkProvider,
    "plugsky": PlugskyProvider,
}


def get_provider(provider_name: str, config_mgr: Any) -> BaseLLMProvider:
    """
    Retorna la instancia del driver dedicado para el proveedor solicitado.
    Si el proveedor no tiene driver exclusivo, usa GenericLLMProvider como respaldo.
    """
    prov_key = (provider_name or "").lower().strip()
    provider_cls = PROVIDER_REGISTRY.get(prov_key)

    if provider_cls:
        return provider_cls(config_mgr)

    return GenericLLMProvider(config_mgr, provider_name=prov_key)
