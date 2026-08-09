import asyncio
import logging
from app.config.settings import get_settings
from app.bot.telegram_service import TelegramService
from app.services.ingestion_service import IngestionService
from app.services.content_service import ContentService
from app.services.idempotency_service import IdempotencyService
from app.database.style_memory import StyleMemory
from app.database.idempotency_store import IdempotencyStore
from app.extractors.text_extractor import TextExtractor
from app.extractors.url_extractor import URLExtractor
from app.extractors.pdf_extractor import PDFExtractor
from app.llm.ollama_client import OllamaClient
from app.llm.validator import LLMValidator
from app.sheets.google_sheets import GoogleSheetsClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def main():
    """
    Main function to initialize and run the Telegram bot and associated services.
    """
    logger.info("Starting Telegram Content Agent...")

    settings = get_settings()
    logger.info("Settings loaded.")

    # Initialize database clients
    style_memory = StyleMemory(settings.STYLE_DB_PATH)
    idempotency_store = IdempotencyStore(settings.GENERATION_DB_PATH)
    logger.info("Database clients initialized.")

    # Initialize extractors
    text_extractor = TextExtractor()
    url_extractor = URLExtractor(settings)
    pdf_extractor = PDFExtractor(settings)
    content_service = ContentService(text_extractor, url_extractor, pdf_extractor)
    logger.info("Content extractors initialized.")

    # Initialize LLM client and validator
    ollama_client = OllamaClient(settings)
    llm_validator = LLMValidator(ollama_client)
    logger.info("LLM client and validator initialized.")

    # Initialize Google Sheets client
    google_sheets_client = GoogleSheetsClient(settings)
    logger.info("Google Sheets client initialized.")

    # Initialize Idempotency Service
    idempotency_service = IdempotencyService(idempotency_store, style_memory)
    logger.info("Idempotency service initialized.")

    # Initialize Ingestion Service
    ingestion_service = IngestionService(
        settings=settings,
        content_service=content_service,
        style_memory=style_memory,
        ollama_client=ollama_client,
        llm_validator=llm_validator,
        google_sheets_client=google_sheets_client,
        idempotency_service=idempotency_service
    )
    logger.info("Ingestion service initialized.")

    # Initialize and run Telegram Service
    telegram_service = TelegramService(settings, ingestion_service, style_memory)
    await telegram_service.run()

    logger.info("Telegram Content Agent stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user (KeyboardInterrupt).")
    except Exception as e:
        logger.critical(f"Unhandled exception in main application: {e}", exc_info=True)
