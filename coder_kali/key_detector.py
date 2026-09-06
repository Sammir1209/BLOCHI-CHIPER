"""
coder_kali/key_detector.py - Detector automático de proveedor de IA a partir de la API Key.
Inspecciona prefijos, formatos y valida contra endpoints de modelos en vivo.
"""

import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (Blood-Cipher/2.0)"

# Firmas y heurísticas directas de API Keys conocidas
PROVIDER_KEY_PATTERNS = [
    # Plugsky AI
    {
        "provider": "plugsky",
        "name": "Plugsky AI (plugsky.com)",
        "check": lambda k: k.startswith("sk-live-") or k.startswith("sk-ps-") or k.startswith("plugsky-") or k.startswith("psk_"),
        "api_base": "https://api.plugsky.com/v1",
        "default_model": "plugsky-pro",
    },
    # BazaarLink AI
    {
        "provider": "bazaarlink",
        "name": "BazaarLink AI (bazaarlink.ai)",
        "check": lambda k: k.startswith("sk-bl-"),
        "api_base": "https://bazaarlink.ai/api/v1",
        "default_model": "deepseek-v3.2",
    },
    # Hugging Face
    {
        "provider": "huggingface",
        "name": "Hugging Face Serverless",
        "check": lambda k: k.startswith("hf_"),
        "api_base": "https://api-inference.huggingface.co/v1",
        "default_model": "huggingface/deepseek-ai/DeepSeek-R1",
    },
    # Groq Cloud
    {
        "provider": "groq",
        "name": "Groq Cloud (Inferencia Ultra Rápida)",
        "check": lambda k: k.startswith("gsk_"),
        "api_base": "https://api.groq.com/openai/v1",
        "default_model": "groq/llama-3.3-70b-versatile",
    },
    # Anthropic Claude
    {
        "provider": "anthropic",
        "name": "Anthropic Claude",
        "check": lambda k: k.startswith("sk-ant-"),
        "api_base": "https://api.anthropic.com/v1",
        "default_model": "anthropic/claude-3-5-sonnet-20241022",
    },
    # OpenRouter
    {
        "provider": "openrouter",
        "name": "OpenRouter Universal",
        "check": lambda k: k.startswith("sk-or-v1-") or k.startswith("sk-or-"),
        "api_base": "https://openrouter.ai/api/v1",
        "default_model": "openrouter/deepseek/deepseek-r1",
    },
    # Google Gemini
    {
        "provider": "gemini",
        "name": "Google Gemini",
        "check": lambda k: k.startswith("AIzaSy"),
        "api_base": "https://generativelanguage.googleapis.com/v1beta",
        "default_model": "gemini/gemini-2.5-flash",
    },
    # xAI (Grok)
    {
        "provider": "xai",
        "name": "xAI (Grok)",
        "check": lambda k: k.startswith("xai-"),
        "api_base": "https://api.x.ai/v1",
        "default_model": "xai/grok-2-latest",
    },
    # Together AI
    {
        "provider": "together",
        "name": "Together AI",
        "check": lambda k: len(k) == 64 and all(c in "0123456789abcdefABCDEF" for c in k),
        "api_base": "https://api.together.xyz/v1",
        "default_model": "together_ai/deepseek-ai/DeepSeek-R1",
    },
    # Cerebras
    {
        "provider": "cerebras",
        "name": "Cerebras Fast Inference",
        "check": lambda k: k.startswith("csk-"),
        "api_base": "https://api.cerebras.ai/v1",
        "default_model": "cerebras/llama3.3-70b",
    },
    # Mistral AI
    {
        "provider": "mistral",
        "name": "Mistral AI",
        "check": lambda k: len(k) == 32 and not k.startswith("sk-") and k.isalnum(),
        "api_base": "https://api.mistral.ai/v1",
        "default_model": "mistral/mistral-large-latest",
    },
]


def test_endpoint_models(url: str, api_key: str) -> Optional[List[str]]:
    """Intenta consultar /models en el endpoint con la key y headers adecuados."""
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                model_list = []
                # Formato standard OpenAI: {"data": [{"id": "..."}, ...]}
                for item in data.get("data", []):
                    m_id = item.get("id") or item.get("name")
                    if m_id:
                        model_list.append(str(m_id))
                return model_list
    except Exception:
        pass
    return None


def detect_provider_and_models(api_key: str) -> Dict[str, Any]:
    """
    Analiza una API Key / Token de IA, descubre automáticamente qué proveedor es,
    valida el acceso en tiempo real y extrae la lista de modelos disponibles.
    
    Retorna un diccionario:
    {
        "success": True/False,
        "provider": "bazaarlink",
        "name": "BazaarLink AI",
        "api_base": "https://bazaarlink.ai/api/v1",
        "default_model": "deepseek-v3.2",
        "models": ["deepseek-v3.2", "qwen3.8-max", ...],
        "message": "Detectado exitosamente"
    }
    """
    key = (api_key or "").strip()
    if not key:
        return {
            "success": False,
            "provider": None,
            "name": "Desconocido",
            "message": "API Key vacía.",
            "models": [],
        }

    # 1. Chequeo por prefijo conocido
    matched_meta = None
    for pattern in PROVIDER_KEY_PATTERNS:
        try:
            if pattern["check"](key):
                matched_meta = pattern
                break
        except Exception:
            continue

    if matched_meta:
        prov = matched_meta["provider"]
        name = matched_meta["name"]
        api_base = matched_meta.get("api_base", "")
        default_model = matched_meta.get("default_model", "")

        # Si tiene endpoint OpenAI-compatible estándar, consultar modelos en vivo
        live_models = []
        if api_base:
            models_url = f"{api_base.rstrip('/')}/models"
            found = test_endpoint_models(models_url, key)
            if found:
                live_models = found

        return {
            "success": True,
            "provider": prov,
            "name": name,
            "api_base": api_base,
            "default_model": default_model or (live_models[0] if live_models else ""),
            "models": live_models,
            "message": f"Proveedor identificado con precisión: {name}",
        }

    # 2. Si empieza por 'sk-', podría ser OpenAI, DeepSeek, AIMLAPI, Puter o un gateway compatible
    if key.startswith("sk-"):
        candidates = [
            ("deepseek", "DeepSeek", "https://api.deepseek.com/models", "https://api.deepseek.com", "deepseek-chat"),
            ("openai", "OpenAI", "https://api.openai.com/v1/models", "https://api.openai.com/v1", "openai/gpt-4o"),
            ("aimlapi", "AIML API", "https://api.aimlapi.com/v1/models", "https://api.aimlapi.com/v1", "openai/deepseek-ai/DeepSeek-R1"),
            ("bazaarlink", "BazaarLink AI", "https://bazaarlink.ai/api/v1/models", "https://bazaarlink.ai/api/v1", "deepseek-v3.2"),
            ("puter", "Puter AI", "https://api.puter.com/puterai/openai/v1/models", "https://api.puter.com/puterai/openai/v1", "deepseek/deepseek-chat"),
        ]
        for prov_id, prov_name, mod_url, base_url, def_mod in candidates:
            models = test_endpoint_models(mod_url, key)
            if models:
                return {
                    "success": True,
                    "provider": prov_id,
                    "name": prov_name,
                    "api_base": base_url,
                    "default_model": def_mod,
                    "models": models,
                    "message": f"Proveedor verificado en vivo con la clave: {prov_name}",
                }

    # 3. Si no se pudo detectar en caliente, retornar fallback genérico
    return {
        "success": False,
        "provider": None,
        "name": "No identificado automáticamente",
        "api_base": "",
        "default_model": "",
        "models": [],
        "message": "No se pudo detectar el proveedor de forma automática a partir de la firma de la clave.",
    }
