"""Database initialization script."""

from backend.db.session import engine, Base, SessionLocal
from backend.db.models import ApiKeyVault, SystemAuditLog
from backend.core.config import settings, encrypt_secret
import datetime


def init_database():
    """Create all tables and seed default configuration if not present."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Check if API vault is initialized
        existing_keys = db.query(ApiKeyVault).count()
        if existing_keys == 0:
            # Seed Gemini keys from environment if present
            gemini_keys = [
                ("GEMINI_KEY_1", settings.GEMINI_API_KEY_1 or ""),
                ("GEMINI_KEY_2", settings.GEMINI_API_KEY_2 or ""),
                ("GEMINI_KEY_3", settings.GEMINI_API_KEY_3 or ""),
            ]
            for idx, (label, raw_key) in enumerate(gemini_keys, start=1):
                if raw_key:
                    vault_entry = ApiKeyVault(
                        provider="gemini",
                        key_label=label,
                        model_name="gemini-2.5-flash",
                        encrypted_key=encrypt_secret(raw_key),
                        priority_order=idx,
                        is_active=True,
                        status="ACTIVE",
                    )
                    db.add(vault_entry)

            # Check Groq / OpenRouter / OpenAI
            if settings.GROQ_API_KEY:
                db.add(ApiKeyVault(
                    provider="groq",
                    key_label="GROQ_PRIMARY",
                    model_name="llama-3.3-70b-versatile",
                    encrypted_key=encrypt_secret(settings.GROQ_API_KEY),
                    priority_order=10,
                    is_active=True,
                    status="ACTIVE",
                ))

            if settings.OPENROUTER_API_KEY:
                db.add(ApiKeyVault(
                    provider="openrouter",
                    key_label="OPENROUTER_FALLBACK",
                    model_name="anthropic/claude-3.5-sonnet",
                    encrypted_key=encrypt_secret(settings.OPENROUTER_API_KEY),
                    priority_order=20,
                    is_active=True,
                    status="ACTIVE",
                ))

            db.commit()

        # Log system initialization event
        audit = SystemAuditLog(
            event_type="SYSTEM_INITIALIZED",
            details_json='{"status": "Database tables verified and WAL mode enabled."}',
            timestamp=datetime.datetime.utcnow(),
        )
        db.add(audit)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
    print("Database successfully initialized.")
