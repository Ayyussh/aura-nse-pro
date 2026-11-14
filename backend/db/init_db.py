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

        # Ensure prev_hash and hash_version columns exist
        with engine.begin() as conn:
            from sqlalchemy import text
            try:
                conn.execute(text("ALTER TABLE predictions ADD COLUMN prev_hash VARCHAR(64) DEFAULT 'GENESIS_AURA_HASH'"))
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE predictions ADD COLUMN hash_version VARCHAR(16) DEFAULT 'v2'"))
            except Exception:
                pass

            # SQLite database triggers to block UPDATE/DELETE on audit ledger
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS abort_update_system_audit_logs
                BEFORE UPDATE ON system_audit_logs
                BEGIN
                    SELECT RAISE(ABORT, 'IMMUTABLE_AUDIT_LOG: UPDATE is strictly prohibited.');
                END;
            """))
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS abort_delete_system_audit_logs
                BEFORE DELETE ON system_audit_logs
                BEGIN
                    SELECT RAISE(ABORT, 'IMMUTABLE_AUDIT_LOG: DELETE is strictly prohibited.');
                END;
            """))
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS abort_delete_predictions
                BEFORE DELETE ON predictions
                BEGIN
                    SELECT RAISE(ABORT, 'IMMUTABLE_PREDICTIONS: DELETE is strictly prohibited on predictions ledger.');
                END;
            """))
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS abort_tamper_prediction_audit
                BEFORE UPDATE OF audit_hash, prev_hash, entry_price, stop_loss, target_price, quantity ON predictions
                BEGIN
                    SELECT RAISE(ABORT, 'IMMUTABLE_PREDICTION_AUDIT: Tampering with trade entry levels or cryptographic hashes is strictly prohibited.');
                END;
            """))

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
