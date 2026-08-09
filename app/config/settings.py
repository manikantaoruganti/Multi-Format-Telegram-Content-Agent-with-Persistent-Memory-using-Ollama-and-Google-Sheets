import os
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Uses Pydantic-settings for validation and type coercion.
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    TELEGRAM_BOT_TOKEN: str = Field(..., description="Telegram bot API token")

    GOOGLE_SHEETS_CREDENTIALS_B64: str = Field(..., description="Base64 encoded Google Service Account JSON")
    GOOGLE_SPREADSHEET_ID: str = Field(..., description="ID of the Google Spreadsheet")
    GOOGLE_WORKSHEET_NAME: str = Field("Content", description="Name of the worksheet to use")

    LLM_PROVIDER: str = Field("ollama", description="LLM provider (e.g., 'ollama')")
    OLLAMA_BASE_URL: str = Field("http://ollama:11434", description="Base URL for Ollama API")
    OLLAMA_MODEL: str = Field("llama3.1", description="Ollama model to use (e.g., 'llama3.1')")
    LLM_TIMEOUT_SECONDS: int = Field(120, description="Timeout for LLM API calls in seconds")

    STYLE_DB_PATH: str = Field("/data/styles.db", description="Path to the SQLite database for user styles")
    GENERATION_DB_PATH: str = Field("/data/generations.db", description="Path to the SQLite database for processed generations")

    HEALTH_HOST: str = Field("0.0.0.0", description="Host for the health check server")
    HEALTH_PORT: int = Field(8080, description="Port for the health check server")

    MAX_RETRIES: int = Field(3, description="Maximum number of retries for transient errors")
    RETRY_DELAY_SECONDS: int = Field(2, description="Initial delay for exponential backoff in seconds")

    MAX_URL_CONTENT_SIZE_MB: int = Field(5, description="Maximum size of extracted URL content in MB")
    MAX_PDF_FILE_SIZE_MB: int = Field(10, description="Maximum size of uploaded PDF files in MB")

@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached instance of the Settings.
    Loads environment variables from .env file if present.
    """
    # Load .env file if it exists
    from dotenv import load_dotenv
    load_dotenv()
    return Settings()
