"""
config.py
=========
Configuración central del proyecto.
Lee variables desde .env — nunca poner keys aquí.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent


class Settings:

    # ── LLM ──────────────────────────────────────────────────
    # "groq" | "gemini" | "anthropic"
    llm_provider: str = os.getenv("LLM_PROVIDER", "groq")
    llm_model: str    = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0"))

    # Claves por proveedor
    groq_api_key:      str = os.getenv("GROQ_API_KEY", "")
    gemini_api_key:    str = os.getenv("GEMINI_API_KEY", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    openai_api_key:    str = os.getenv("OPENAI_API_KEY", "")

    # ── Backend de datos ──────────────────────────────────────
    # "local" → DuckDB sobre CSVs
    # "aws"   → Athena + DynamoDB
    db_backend: str = os.getenv("DB_BACKEND", "local")

    # ── Rutas ─────────────────────────────────────────────────
    data_path:     Path = BASE_DIR / os.getenv("DATA_PATH", "data")
    policies_path: Path = BASE_DIR / os.getenv("POLICIES_PATH", "policies")

    # ── AWS (solo si db_backend="aws") ────────────────────────
    aws_region:      str = os.getenv("AWS_REGION", "us-east-1")
    aws_s3_bucket:   str = os.getenv("AWS_S3_BUCKET", "")
    athena_database: str = os.getenv("ATHENA_DATABASE", "strata_challenge")
    athena_output:   str = os.getenv("ATHENA_OUTPUT_LOCATION", "")

    # ── Agente ────────────────────────────────────────────────
    max_response_seconds: int = int(os.getenv("MAX_RESPONSE_SECONDS", "8"))

    def validate(self) -> None:
        """Verifica configuración mínima. Llamar al inicio de create_agent()."""
        provider = self.llm_provider.lower()

        if provider == "groq" and not self.groq_api_key:
            raise ValueError(
                "GROQ_API_KEY no configurada.\n"
                "Agrégala al .env o cambia LLM_PROVIDER."
            )
        if provider == "gemini" and not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY no configurada.")
        if provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY no configurada.")

        if not self.data_path.exists():
            raise FileNotFoundError(
                f"Carpeta de datos no encontrada: {self.data_path}\n"
                "Copia los CSVs del challenge a data/"
            )
        if not self.policies_path.exists():
            raise FileNotFoundError(
                f"Carpeta de políticas no encontrada: {self.policies_path}\n"
                "Copia los Markdowns del challenge a policies/"
            )


settings = Settings()