from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BioAuth Gateway"
    debug: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./bioauth.db"

    # Vector DB (ChromaDB)
    chroma_persist_dir: str = "./chroma_data"

    # Transport
    transport_mode: str = "simulate"  # "simulate", "http", or "bluetooth"
    edge_http_url: str = "http://localhost:8001"
    edge_bluetooth_address: str = ""

    # Security
    api_secret_key: str = "bioauth-dev-secret-change-in-production"
    api_key_header: str = "X-API-Key"
    api_keys: list[str] = ["dev-api-key-001"]

    # Scoring thresholds
    identity_threshold: float = 0.75
    anomaly_threshold: float = 2.5
    signal_quality_threshold: float = 0.5

    # Enrollment
    enrollment_samples: int = 3

    # Optional — same .env as demo; gateway does not use these (demo reads AUTH0_* via its own loader)
    auth0_domain: str | None = None
    auth0_client_id: str | None = None

    model_config = SettingsConfigDict(
        env_prefix="BIOAUTH_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
