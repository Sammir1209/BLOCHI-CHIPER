"""
coder_kali/config.py - Gestor de Configuración, Credenciales y Modelos.
Almacena la configuración en ~/.config/blood-cipher/config.json con permisos seguros.
"""

import os
import json
import base64
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional

CONFIG_DIR = Path.home() / ".config" / "blood-cipher"
if not CONFIG_DIR.exists() and (Path.home() / ".config" / "coder-kali").exists():
    CONFIG_DIR = Path.home() / ".config" / "coder-kali"

CONFIG_FILE = CONFIG_DIR / "config.json"
SECRET_KEY_FILE = CONFIG_DIR / ".secret.key"

DEFAULT_PROVIDERS = {
    "gemini": {
        "name": "Google Gemini",
        "default_model": "gemini/gemini-2.5-flash",
        "available_models": [
            "gemini/gemini-3.6-flash",
            "gemini/gemini-2.5-flash",
            "gemini/gemini-2.5-pro",
            "gemini/gemini-1.5-flash",
            "gemini/gemini-1.5-pro",
        ],
        "free_models": [
            "gemini/gemini-2.5-flash",
            "gemini/gemini-1.5-flash",
        ],
        "env_var": "GEMINI_API_KEY",
        "requires_api_key": True,
    },
    "anthropic": {
        "name": "Anthropic Claude",
        "default_model": "anthropic/claude-3-5-sonnet-20241022",
        "available_models": [
            "anthropic/claude-3-5-sonnet-20241022",
            "anthropic/claude-3-5-haiku-20241022",
            "anthropic/claude-3-opus-20240229",
            "anthropic/claude-3-sonnet-20240229",
            "anthropic/claude-3-haiku-20240307",
        ],
        "free_models": [
            "anthropic/claude-3-5-haiku-20241022",
        ],
        "env_var": "ANTHROPIC_API_KEY",
        "requires_api_key": True,
    },
    "openai": {
        "name": "OpenAI",
        "default_model": "openai/gpt-4o-mini",
        "available_models": [
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "openai/o3-mini",
            "openai/o1",
            "openai/o1-mini",
            "openai/gpt-4-turbo",
            "openai/gpt-3.5-turbo",
        ],
        "free_models": [
            "openai/gpt-4o-mini",
            "openai/gpt-3.5-turbo",
        ],
        "env_var": "OPENAI_API_KEY",
        "requires_api_key": True,
    },
    "deepseek": {
        "name": "DeepSeek",
        "default_model": "deepseek/deepseek-chat",
        "available_models": [
            "deepseek/deepseek-chat",
            "deepseek/deepseek-reasoner",
            "deepseek/deepseek-coder",
        ],
        "free_models": [
            "deepseek/deepseek-chat",
            "deepseek/deepseek-reasoner",
        ],
        "env_var": "DEEPSEEK_API_KEY",
        "requires_api_key": True,
    },
    "groq": {
        "name": "Groq (Inferencia Ultra Rápida)",
        "default_model": "groq/llama-3.3-70b-versatile",
        "available_models": [
            "groq/llama-3.3-70b-versatile",
            "groq/llama-3.1-8b-instant",
            "groq/llama-3.2-11b-vision-preview",
            "groq/llama-3.2-3b-preview",
            "groq/llama-3.2-1b-preview",
            "groq/qwen-qwq-32b",
            "groq/mixtral-8x7b-32768",
            "groq/gemma2-9b-it",
            "groq/deepseek-r1-distill-llama-70b",
        ],
        "free_models": [
            "groq/llama-3.3-70b-versatile",
            "groq/llama-3.1-8b-instant",
            "groq/gemma2-9b-it",
            "groq/mixtral-8x7b-32768",
            "groq/deepseek-r1-distill-llama-70b",
        ],
        "env_var": "GROQ_API_KEY",
        "requires_api_key": True,
    },
    "mistral": {
        "name": "Mistral AI",
        "default_model": "mistral/mistral-small-latest",
        "available_models": [
            "mistral/mistral-large-latest",
            "mistral/codestral-latest",
            "mistral/mistral-small-latest",
            "mistral/pixtral-large-latest",
            "mistral/open-mistral-nemo",
            "mistral/open-codestral-mamba",
        ],
        "free_models": [
            "mistral/open-mistral-nemo",
            "mistral/open-codestral-mamba",
            "mistral/mistral-small-latest",
        ],
        "env_var": "MISTRAL_API_KEY",
        "requires_api_key": True,
    },
    "xai": {
        "name": "xAI (Grok)",
        "default_model": "xai/grok-beta",
        "available_models": [
            "xai/grok-2-latest",
            "xai/grok-2-vision-1212",
            "xai/grok-beta",
        ],
        "free_models": [
            "xai/grok-beta",
        ],
        "env_var": "XAI_API_KEY",
        "requires_api_key": True,
    },
    "cohere": {
        "name": "Cohere",
        "default_model": "cohere/command-r",
        "available_models": [
            "cohere/command-r-plus",
            "cohere/command-r",
            "cohere/command-light",
            "cohere/command",
        ],
        "free_models": [
            "cohere/command-light",
            "cohere/command-r",
        ],
        "env_var": "COHERE_API_KEY",
        "requires_api_key": True,
    },
    "perplexity": {
        "name": "Perplexity AI",
        "default_model": "perplexity/sonar",
        "available_models": [
            "perplexity/sonar-reasoning-pro",
            "perplexity/sonar-reasoning",
            "perplexity/sonar-pro",
            "perplexity/sonar",
        ],
        "free_models": [
            "perplexity/sonar",
        ],
        "env_var": "PERPLEXITYAI_API_KEY",
        "requires_api_key": True,
    },
    "together": {
        "name": "Together AI",
        "default_model": "together_ai/meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "available_models": [
            "together_ai/meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "together_ai/deepseek-ai/DeepSeek-R1",
            "together_ai/Qwen/Qwen2.5-Coder-32B-Instruct",
            "together_ai/mistralai/Mixtral-8x22B-Instruct-v0.1",
        ],
        "free_models": [
            "together_ai/meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "together_ai/Qwen/Qwen2.5-Coder-32B-Instruct",
        ],
        "env_var": "TOGETHERAI_API_KEY",
        "requires_api_key": True,
    },
    "cerebras": {
        "name": "Cerebras (Hardware Especializado)",
        "default_model": "cerebras/llama3.1-8b",
        "available_models": [
            "cerebras/llama3.3-70b",
            "cerebras/llama3.1-8b",
        ],
        "free_models": [
            "cerebras/llama3.1-8b",
            "cerebras/llama3.3-70b",
        ],
        "env_var": "CEREBRAS_API_KEY",
        "requires_api_key": True,
    },
    "qwen": {
        "name": "Alibaba Qwen (DashScope)",
        "default_model": "qwen/qwen-turbo",
        "available_models": [
            "qwen/qwen2.5-coder-32b-instruct",
            "qwen/qwen-max",
            "qwen/qwen-plus",
            "qwen/qwen-turbo",
            "qwen/qwen2.5-72b-instruct",
        ],
        "free_models": [
            "qwen/qwen-turbo",
            "qwen/qwen2.5-coder-32b-instruct",
        ],
        "env_var": "DASHSCOPE_API_KEY",
        "requires_api_key": True,
    },
    "huggingface": {
        "name": "Hugging Face Serverless",
        "default_model": "huggingface/deepseek-ai/DeepSeek-R1",
        "available_models": [
            "huggingface/deepseek-ai/DeepSeek-R1",
            "huggingface/meta-llama/Llama-3.3-70B-Instruct",
            "huggingface/Qwen/Qwen2.5-Coder-32B-Instruct",
            "huggingface/mistralai/Mistral-7B-Instruct-v0.3",
        ],
        "free_models": [
            "huggingface/deepseek-ai/DeepSeek-R1",
            "huggingface/meta-llama/Llama-3.3-70B-Instruct",
            "huggingface/Qwen/Qwen2.5-Coder-32B-Instruct",
            "huggingface/mistralai/Mistral-7B-Instruct-v0.3",
        ],
        "env_var": "HUGGINGFACE_API_KEY",
        "requires_api_key": True,
    },
    "ollama": {
        "name": "Ollama (100% Local / Offline / Sin Internet)",
        "default_model": "ollama/llama3.3",
        "available_models": [
            "ollama/llama3.3",
            "ollama/llama3.2",
            "ollama/deepseek-r1",
            "ollama/qwen2.5-coder:7b",
            "ollama/qwen2.5-coder:32b",
            "ollama/mistral",
            "ollama/codellama",
            "ollama/starcoder2",
        ],
        "free_models": [
            "ollama/llama3.3",
            "ollama/llama3.2",
            "ollama/deepseek-r1",
            "ollama/qwen2.5-coder:7b",
            "ollama/qwen2.5-coder:32b",
            "ollama/mistral",
            "ollama/codellama",
            "ollama/starcoder2",
        ],
        "env_var": "OLLAMA_API_BASE",
        "requires_api_key": False,
        "default_api_base": "http://localhost:11434",
    },
    "bai": {
        "name": "Bai Chat (chat.b.ai API)",
        "default_model": "openai/deepseek-chat",
        "available_models": [
            "openai/gpt-5.2",
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "openai/chatgpt-4o-latest",
            "openai/claude-3-5-sonnet",
            "openai/deepseek-chat",
            "openai/deepseek-reasoner",
        ],
        "free_models": [
            "openai/deepseek-chat",
            "openai/deepseek-reasoner",
            "openai/gpt-4o-mini",
        ],
        "env_var": "BAI_API_KEY",
        "requires_api_key": True,
        "default_api_base": "https://api.b.ai/v1",
    },
    "openrouter": {
        "name": "OpenRouter (Acceso Universal a 200+ Modelos)",
        "default_model": "openrouter/deepseek/deepseek-r1:free",
        "available_models": [
            "openrouter/deepseek/deepseek-r1:free",
            "openrouter/deepseek/deepseek-chat:free",
            "openrouter/meta-llama/llama-3.3-70b-instruct:free",
            "openrouter/qwen/qwen-2.5-coder-32b-instruct:free",
            "openrouter/google/gemini-2.0-flash-exp:free",
            "openrouter/deepseek/deepseek-r1",
            "openrouter/deepseek/deepseek-chat",
            "openrouter/deepseek/deepseek-r1-distill-llama-70b",
            "openrouter/deepseek/deepseek-r1-distill-qwen-32b",
            "openrouter/qwen/qwen-2.5-coder-32b-instruct",
            "openrouter/meta-llama/llama-3.3-70b-instruct",
            "openrouter/anthropic/claude-3.5-sonnet",
            "openrouter/openai/gpt-4o",
            "openrouter/google/gemini-2.0-flash-001",
        ],
        "free_models": [
            "openrouter/deepseek/deepseek-r1:free",
            "openrouter/deepseek/deepseek-chat:free",
            "openrouter/meta-llama/llama-3.3-70b-instruct:free",
            "openrouter/qwen/qwen-2.5-coder-32b-instruct:free",
            "openrouter/google/gemini-2.0-flash-exp:free",
        ],
        "env_var": "OPENROUTER_API_KEY",
        "requires_api_key": True,
    },
    "aimlapi": {
        "name": "AIML API (aimlapi.com - 300+ Modelos de IA)",
        "default_model": "openai/deepseek-ai/DeepSeek-R1",
        "available_models": [
            "openai/deepseek-ai/DeepSeek-R1",
            "openai/deepseek-ai/DeepSeek-V3",
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "openai/o1-mini",
            "openai/o3-mini",
            "openai/claude-3-5-sonnet-20241022",
            "openai/claude-3-5-haiku-20241022",
            "openai/meta-llama/Llama-3.3-70B-Instruct",
            "openai/Qwen/Qwen2.5-Coder-32B-Instruct",
            "openai/mistralai/Mistral-Large-2407",
        ],
        "free_models": [
            "openai/deepseek-ai/DeepSeek-V3",
            "openai/gpt-4o-mini",
        ],
        "env_var": "AIMLAPI_API_KEY",
        "requires_api_key": True,
        "default_api_base": "https://api.aimlapi.com/v1",
    },
    "puter": {
        "name": "Puter.js (DeepSeek Ilimitado & 500+ Modelos)",
        "default_model": "deepseek/deepseek-chat",
        "available_models": [
            "deepseek/deepseek-chat",
            "deepseek/deepseek-reasoner",
            "deepseek/deepseek-r1-0528",
            "deepseek/deepseek-v4-flash",
            "deepseek/deepseek-v4-pro",
            "deepseek/deepseek-v4-flash-vision-exp",
            "deepseek/deepseek-v4-pro-0813",
            "deepseek/deepseek-v4-flash-0731",
            "deepseek/deepseek-v3.2",
            "deepseek/deepseek-chat-v3.1",
            "claude-3-5-sonnet",
            "claude-3-5-haiku",
            "gpt-4o",
            "gpt-4o-mini",
            "o3-mini",
        ],
        "free_models": [
            "deepseek/deepseek-chat",
            "deepseek/deepseek-reasoner",
            "deepseek/deepseek-r1-0528",
            "deepseek/deepseek-v4-flash",
            "deepseek/deepseek-v4-pro",
            "deepseek/deepseek-v3.2",
            "claude-3-5-haiku",
            "gpt-4o-mini",
        ],
        "env_var": "PUTER_AUTH_TOKEN",
        "requires_api_key": True,
        "default_api_base": "https://api.puter.com/puterai/openai/v1",
    },
    "bazaarlink": {
        "name": "BazaarLink AI (bazaarlink.ai)",
        "default_model": "auto:free",
        "available_models": [
            "auto:free",
            "deepseek-v3.2",
            "deepseek-v4-flash",
            "deepseek-v4-pro",
            "qwen3.8-max",
            "glm-5.1",
            "glm-4.7",
            "kimi-k2.7-code",
            "minimax-m2.7",
        ],
        "free_models": [
            "auto:free",
        ],
        "env_var": "BAZAARLINK_API_KEY",
        "requires_api_key": True,
        "default_api_base": "https://bazaarlink.ai/api/v1",
    },
    "plugsky": {
        "name": "Plugsky AI (plugsky.com - 30+ Modelos)",
        "default_model": "plugsky-pro",
        "available_models": [
            "plugsky-pro",
            "plugsky-frontier",
            "plugsky-micro",
            "plugsky-lite",
            "plugsky-max",
            "deepseek-r1",
            "deepseek-v3",
            "mistral-large-3",
            "llama-3.3-70b",
            "qwen-2.5-72b",
        ],
        "free_models": [
            "plugsky-micro",
            "plugsky-lite",
        ],
        "env_var": "PLUGSKY_API_KEY",
        "requires_api_key": True,
        "default_api_base": "https://api.plugsky.com/v1",
    },
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "provider": "gemini",
    "model": "gemini/gemini-2.5-flash",
    "temperature": 0.2,
    "max_tokens": 4096,
    "api_keys": {},
    "api_bases": {
        "ollama": "http://localhost:11434"
    },
    "auto_approve_safe_commands": False,
    "theme": "cyberpunk",
    "system_prompt_mode": "default",
}


class ConfigManager:
    """Administrador de configuración persistente con cifrado local."""

    def __init__(self):
        self._ensure_config_dir()
        self._cipher = self._get_or_create_cipher()
        self.config = self._load()

    def _ensure_config_dir(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            # Permisos estrictos 0700 en Linux/Unix
            os.chmod(CONFIG_DIR, 0o700)
        except Exception:
            pass

    def _get_or_create_cipher(self):
        try:
            from cryptography.fernet import Fernet
            if not SECRET_KEY_FILE.exists():
                key = Fernet.generate_key()
                SECRET_KEY_FILE.write_bytes(key)
                try:
                    os.chmod(SECRET_KEY_FILE, 0o600)
                except Exception:
                    pass
            else:
                key = SECRET_KEY_FILE.read_bytes()
            return Fernet(key)
        except Exception:
            return None

    def _encrypt(self, plain_text: str) -> str:
        if not plain_text:
            return ""
        if self._cipher:
            try:
                return self._cipher.encrypt(plain_text.encode("utf-8")).decode("utf-8")
            except Exception:
                pass
        # Fallback de codificación simple
        return "b64:" + base64.b64encode(plain_text.encode("utf-8")).decode("utf-8")

    def _decrypt(self, cipher_text: str) -> str:
        if not cipher_text:
            return ""
        if cipher_text.startswith("b64:"):
            try:
                return base64.b64decode(cipher_text[4:].encode("utf-8")).decode("utf-8")
            except Exception:
                return cipher_text
        if self._cipher:
            try:
                return self._cipher.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
            except Exception:
                pass
        return cipher_text

    def _load(self) -> Dict[str, Any]:
        if not CONFIG_FILE.exists():
            cfg = DEFAULT_CONFIG.copy()
            self._save_raw(cfg)
            return cfg
        try:
            from coder_kali.fast_engine import fast_json_loads
            data = fast_json_loads(CONFIG_FILE.read_bytes())
            merged = DEFAULT_CONFIG.copy()
            merged.update(data)
            return merged
        except Exception:
            return DEFAULT_CONFIG.copy()

    def _save_raw(self, cfg: Dict[str, Any]):
        try:
            from coder_kali.fast_engine import fast_json_dumps
            CONFIG_FILE.write_text(fast_json_dumps(cfg, indent=True), encoding="utf-8")
            try:
                os.chmod(CONFIG_FILE, 0o600)
            except Exception:
                pass
        except Exception as e:
            print(f"[!] Error al guardar configuración: {e}")

    def save(self):
        self._save_raw(self.config)

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        self.config[key] = value
        self.save()

    def set_api_key(self, provider: str, raw_key: str):
        """Guardar una sola API key (compatibilidad)."""
        if "api_keys" not in self.config:
            self.config["api_keys"] = {}
        clean_key = raw_key.strip()
        self.config["api_keys"][provider] = self._encrypt(clean_key)
        self.save()
        env_var = DEFAULT_PROVIDERS.get(provider, {}).get("env_var")
        if env_var and clean_key:
            os.environ[env_var] = clean_key

    def set_api_keys(self, provider: str, raw_keys: list):
        """Guardar múltiples API keys para un proveedor (rotación automática)."""
        if "api_keys_pool" not in self.config:
            self.config["api_keys_pool"] = {}
        if "api_key_index" not in self.config:
            self.config["api_key_index"] = {}
        encrypted = [self._encrypt(k.strip()) for k in raw_keys if k.strip()]
        self.config["api_keys_pool"][provider] = encrypted
        self.config["api_key_index"][provider] = 0
        # También guardar la primera como key principal (compatibilidad)
        if encrypted:
            self.config.setdefault("api_keys", {})[provider] = encrypted[0]
        self.save()
        env_var = DEFAULT_PROVIDERS.get(provider, {}).get("env_var")
        if env_var and raw_keys:
            os.environ[env_var] = raw_keys[0].strip()

    def get_all_api_keys(self, provider: Optional[str] = None) -> list:
        """Obtener todas las API keys desencriptadas del pool de un proveedor."""
        prov = provider or self.config.get("provider", "gemini")
        pool = self.config.get("api_keys_pool", {}).get(prov, [])
        if pool:
            return [self._decrypt(k) for k in pool if k]
        # Fallback: usar la key única como pool de 1
        single = self.get_api_key(prov)
        return [single] if single else []

    def get_api_key_count(self, provider: Optional[str] = None) -> int:
        """Retorna cuántas API keys hay configuradas para un proveedor."""
        return len(self.get_all_api_keys(provider))

    def rotate_api_key(self, provider: Optional[str] = None) -> str:
        """Rotar a la siguiente API key disponible. Retorna la nueva key activa."""
        prov = provider or self.config.get("provider", "gemini")
        keys = self.get_all_api_keys(prov)
        if len(keys) <= 1:
            return keys[0] if keys else ""
        
        if "api_key_index" not in self.config:
            self.config["api_key_index"] = {}
        
        current_idx = self.config["api_key_index"].get(prov, 0)
        new_idx = (current_idx + 1) % len(keys)
        self.config["api_key_index"][prov] = new_idx
        
        new_key = keys[new_idx]
        # Actualizar la key principal y env var
        self.config.setdefault("api_keys", {})[prov] = self.config["api_keys_pool"][prov][new_idx]
        self.save()
        
        env_var = DEFAULT_PROVIDERS.get(prov, {}).get("env_var")
        if env_var and new_key:
            os.environ[env_var] = new_key.strip()
        
        return new_key

    def get_current_key_index(self, provider: Optional[str] = None) -> int:
        """Retorna el índice de la key actualmente activa."""
        prov = provider or self.config.get("provider", "gemini")
        return self.config.get("api_key_index", {}).get(prov, 0)

    def get_api_key(self, provider: Optional[str] = None) -> str:
        prov = provider or self.config.get("provider", "gemini")
        # 1. Priorizar clave guardada explícitamente por el usuario
        encrypted_key = self.config.get("api_keys", {}).get(prov, "")
        if encrypted_key:
            key = self._decrypt(encrypted_key)
            if key and len(key.strip()) > 3:
                return key.strip()

        # 2. Revisar variable de entorno si no está en config
        env_var = DEFAULT_PROVIDERS.get(prov, {}).get("env_var")
        if env_var and os.environ.get(env_var):
            return os.environ[env_var].strip()

        return ""

    def set_provider(self, provider: str, model: Optional[str] = None):
        self.config["provider"] = provider
        if model:
            self.config["model"] = model
        else:
            default_mod = DEFAULT_PROVIDERS.get(provider, {}).get("default_model")
            if default_mod:
                self.config["model"] = default_mod
        self.save()

    def set_model(self, model: str):
        self.config["model"] = model
        self.save()

    def get_active_provider(self) -> str:
        return self.config.get("provider", "gemini")

    def get_active_model(self) -> str:
        return self.config.get("model", "gemini/gemini-2.0-flash")

    def get_api_base(self, provider: Optional[str] = None) -> Optional[str]:
        prov = provider or self.get_active_provider()
        base = self.config.get("api_bases", {}).get(prov)
        if base:
            base = base.strip().rstrip("/")
            if base.endswith("/chat/completions"):
                base = base[:-len("/chat/completions")].rstrip("/")
        return base

    def get_free_models(self, provider: Optional[str] = None) -> list:
        """Retorna la lista de modelos gratuitos disponibles para el proveedor."""
        prov = provider or self.get_active_provider()
        prov_info = DEFAULT_PROVIDERS.get(prov, {})
        free = prov_info.get("free_models", [])
        if free:
            return list(free)
        # Fallback heurístico: buscar modelos con ':free' o 'free' en el nombre
        all_models = prov_info.get("available_models", [])
        return [m for m in all_models if ":free" in m.lower() or "free" in m.lower()]

    def is_configured(self) -> bool:
        provider = self.get_active_provider()
        prov_info = DEFAULT_PROVIDERS.get(provider, {})
        if not prov_info.get("requires_api_key", True):
            return True
        key = self.get_api_key(provider)
        return bool(key and len(key.strip()) > 5)

    def reset(self):
        self.config = DEFAULT_CONFIG.copy()
        self.save()
