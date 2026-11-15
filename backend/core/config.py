"""AURA-NSE Pro Core Configuration Module.

Loads environment variables, YAML strategy/cost/tax configurations,
computes configuration hashes for immutable auditing, and provides
encryption helpers for API key vault.
"""

from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "development"
    APP_SECRET_KEY: str = "aura_default_secret_key_change_me_in_prod"
    FERNET_ENCRYPTION_KEY: str = ""
    DATABASE_URL: str = f"sqlite:///{PROJECT_ROOT / 'backend' / 'aura_nse.db'}"
    TIMEZONE: str = "Asia/Kolkata"
    PORT: int = 8000
    HOST: str = "127.0.0.1"

    ADMIN_USERNAME: str = "investor"
    ADMIN_PASSWORD: str = "aura_nse_secure_pass_2026"

    # LLM keys
    GEMINI_API_KEY_1: Optional[str] = None
    GEMINI_API_KEY_2: Optional[str] = None
    GEMINI_API_KEY_3: Optional[str] = None

    GROQ_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Alerts
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None

    # Capital defaults
    INITIAL_CAPITAL: float = 100000.0
    MAX_RISK_PER_TRADE_PCT: float = 1.5


settings = Settings()

# Fernet cipher initialization
if not settings.FERNET_ENCRYPTION_KEY:
    # Generate fallback key for development if not provided
    generated = Fernet.generate_key().decode()
    fernet_cipher = Fernet(generated.encode())
else:
    fernet_cipher = Fernet(settings.FERNET_ENCRYPTION_KEY.encode())


def encrypt_secret(plain_text: str) -> str:
    """Encrypt a secret string using Fernet."""
    if not plain_text:
        return ""
    return fernet_cipher.encrypt(plain_text.encode()).decode()


def decrypt_secret(cipher_text: str) -> str:
    """Decrypt a secret string using Fernet."""
    if not cipher_text:
        return ""
    return fernet_cipher.decrypt(cipher_text.encode()).decode()


def mask_secret(secret: Optional[str]) -> str:
    """Mask a secret key for UI display (e.g., sk-...4a9f)."""
    if not secret or len(secret) < 8:
        return "********" if secret else ""
    return f"{secret[:4]}...{secret[-4:]}"


def load_yaml_config(file_name: str) -> Dict[str, Any]:
    """Load a YAML configuration file from config/ directory."""
    file_path = CONFIG_DIR / file_name
    if not file_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_strategy_config() -> Dict[str, Any]:
    return load_yaml_config("strategy.yaml")


def get_charges_config() -> Dict[str, Any]:
    return load_yaml_config("charges.yaml")


def get_tax_config() -> Dict[str, Any]:
    return load_yaml_config("tax.yaml")


def get_groups_config() -> Dict[str, Any]:
    file_path = CONFIG_DIR / "groups.yaml"
    if not file_path.exists():
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def compute_config_hash() -> str:
    """Compute deterministic SHA-256 hash of all configuration files."""
    combined = {
        "strategy": get_strategy_config(),
        "charges": get_charges_config(),
        "tax": get_tax_config(),
        "groups": get_groups_config(),
    }
    encoded = json.dumps(combined, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]
