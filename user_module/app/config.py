import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # AWS S3 Configuration
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "product-raw-i"
    S3_FOLDER_PREFIX: str = "uploads/"

    # LLM Configuration (for text extraction)
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"

    # File Processing
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: list = ["jpg", "jpeg", "pdf", "txt", "json", "xlsx"]

    # Database
    DATABASE_PATH: str = "user_module.db"

    # Authentication
    AUTH_USERNAME: str = "admin"
    AUTH_PASSWORD: str = "admin123"
    SECRET_KEY: str = "your-secret-key-change-in-production"
    SESSION_EXPIRE_HOURS: int = 24

    # OpenSearch Configuration (for WhatsApp Bot Knowledge Base)
    OPENSEARCH_HOST: str = "localhost"
    OPENSEARCH_PORT: int = 9200
    OPENSEARCH_USERNAME: str = "admin"
    OPENSEARCH_PASSWORD: str = "admin"
    OPENSEARCH_USE_SSL: bool = True
    OPENSEARCH_VERIFY_CERTS: bool = False
    OPENSEARCH_INDEX_NAME: str = "whatsapp_knowledge_base"

    # Embedding Provider Configuration
    # Options: "gemini", "ollama"
    EMBEDDING_PROVIDER: str = "ollama"

    # Google Gemini Configuration (for embeddings)
    GOOGLE_API_KEY: str = ""
    GEMINI_EMBEDDING_MODEL: str = "models/text-embedding-004"

    # Ollama Configuration (for local embeddings)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_TIMEOUT: int = 60

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
