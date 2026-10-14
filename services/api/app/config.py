from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Compose supplies the real connection string; direct local execution must
    # configure DATABASE_URL explicitly.
    database_url: str = "postgresql+psycopg://kaal@localhost:5432/kaal_ase"
    redis_url: str = "redis://localhost:6379/0"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    qdrant_url: str = "http://localhost:6333"
    object_storage_endpoint: str = "http://localhost:9000"
    object_storage_bucket: str = "kaal-evidence"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma2:2b"
    ollama_embed_model: str = "nomic-embed-text"

    # The API fails closed if KAAL_API_KEY is not configured.
    kaal_api_key: str = ""
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"


settings = Settings()
