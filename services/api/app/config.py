from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://kaal:kaal@localhost:5432/kaal_ase"
    redis_url: str = "redis://localhost:6379/0"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "kaalpassword"
    qdrant_url: str = "http://localhost:6333"
    object_storage_endpoint: str = "http://localhost:9000"
    object_storage_bucket: str = "kaal-evidence"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma2:2b"
    ollama_embed_model: str = "nomic-embed-text"


settings = Settings()

