from typing import Optional

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Azure OpenAI Configuration
    azure_openai_api_key: str
    azure_openai_api_version: str = "2024-12-01-preview"
    azure_openai_endpoint: str
    azure_openai_deployment: str
    azure_openai_triage_model: str
    azure_openai_care_nav_model: str
    azure_openai_embedding_model: str
    
    # Azure Authentication (for Cosmos DB AAD/Entra - optional if using key auth)
    azure_tenant_id: Optional[str] = None
    azure_client_id: Optional[str] = None
    azure_client_secret: Optional[str] = None
    
    # Cosmos DB Configuration (for agent memory/chat history)
    cosmos_endpoint: str
    cosmos_key: Optional[str] = None  # Optional - for Primary Key auth (emulator/dev)
    cosmos_database_name: str = "dr_indigo"
    cosmos_container_name: str = "chat_messages"
    cosmos_max_messages: Optional[int] = 100  # Maximum messages to retain per thread
    
    # AI Search Configuration (Optional)
    search_api_key: Optional[str] = None
    search_endpoint: Optional[str] = None
    search_index_name: Optional[str] = None
    
    # Langfuse Configuration (Optional)
    langfuse_secret_key: Optional[str] = None
    langfuse_public_key: Optional[str] = None
    langfuse_host: Optional[str] = None


def _compile_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        missing = ", ".join(sorted({str(error["loc"][0]) for error in exc.errors()}))
        raise RuntimeError(
            f"Environment variable validation error; missing or invalid values for: {missing}"
        ) from exc


AUBREY_SETTINGS = _compile_settings()
