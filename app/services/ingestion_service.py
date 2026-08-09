import logging
from datetime import datetime
from telegram import Document
from telegram.ext import ContextTypes

from app.config.settings import Settings
from app.services.content_service import ContentService, ContentServiceError
from app.services.idempotency_service import IdempotencyService
from app.database.style_memory import StyleMemory
from app.llm.ollama_client import OllamaClient, LLMClientError
from app.llm.validator import LLMValidator, LLMValidationException
from app.llm.prompts import SYSTEM_PROMPT_TEMPLATE, USER_PROMPT_TEMPLATE
from app.sheets.google_sheets import GoogleSheetsClient, GoogleSheetsError
from app.models.content import ProcessedContent, IngestedContent

logger = logging.getLogger(__name__)

class IngestionService:
    """
    Orchestrates the entire content ingestion, processing, LLM generation,
    validation, and Google Sheets writing pipeline.
    """
    def __init__(
        self,
        settings: Settings,
        content_service: ContentService,
        style_memory: StyleMemory,
        ollama_client: OllamaClient,
        llm_validator: LLMValidator,
        google_sheets_client: GoogleSheetsClient,
        idempotency_service: IdempotencyService
    ):
        self.settings = settings
        self.content_service = content_service
        self.style_memory = style_memory
        self.ollama_client = ollama_client
        self.llm_validator = llm_validator
        self.google_sheets_client = google_sheets_client
        self.idempotency_service = idempotency_service

    async def _send_telegram_message(self, chat_id: int, message: str, context: ContextTypes.DEFAULT_TYPE | None = None) -> None:
        """Helper to send a message back to the Telegram user."""
        if context:
            await context.bot.send_message(chat_id=chat_id, text=message)
        else:
            # Fallback if context is not directly available (e.g., in tests)
            logger.warning(f"Attempted to send Telegram message to {chat_id} without context: {message}")

    async def _process_content_pipeline(self, user_id: int, chat_id: int, ingested_content: IngestedContent) -> None:
        """
        Executes the core content processing pipeline:
        1. Idempotency check
        2. Style retrieval
        3. LLM generation
        4. LLM output validation and correction
        5. Google Sheets write
        """
        submission_timestamp = datetime.now().isoformat()

        # 1. Idempotency Check
        generation_key, style_hash = await self.idempotency_service.generate_generation_key(user_id, ingested_content.source_identifier)
        if not await self.idempotency_service.check_and_record_generation(generation_key, user_id, ingested_content.source_identifier, style_hash):
            await self._send_telegram_message(chat_id, "This content with your current style has already been processed. No new entry created.")
            return

        # 2. Retrieve User Style
        user_style = await self.style_memory.get_style(user_id)
        if not user_style:
            user_style = "neutral, professional tone" # Default style if none set
            logger.info(f"User {user_id} has no custom style, using default.")

        # 3. LLM Generation
        try:
            user_prompt = USER_PROMPT_TEMPLATE.format(
                content_type=ingested_content.content_type.upper(),
                source_content=ingested_content.extracted_content,
                user_style=user_style
            )
            raw_llm_response = await self.ollama_client.generate_content(
                system_prompt=SYSTEM_PROMPT_TEMPLATE,
                user_prompt=user_prompt,
                format_json=True
            )
        except LLMClientError as e:
            logger.error(f"LLM generation failed for user {user_id}, source {ingested_content.source_identifier}: {e}")
            await self._send_telegram_message(chat_id, f"Failed to generate content with LLM: {e}")
            return

        # 4. LLM Output Validation and Correction
        try:
            llm_output = await self.llm_validator.validate_and_correct(
                raw_llm_response=raw_llm_response,
                system_prompt=SYSTEM_PROMPT_TEMPLATE,
                user_prompt=user_prompt, # Pass original user prompt for correction context
                user_style=user_style,
                max_retries=self.settings.MAX_RETRIES
            )
            logger.info(f"LLM output validated for user {user_id}, source {ingested_content.source_identifier}.")
        except LLMValidationException as e:
            logger.error(f"LLM output validation failed after retries for user {user_id}, source {ingested_content.source_identifier}: {e}")
            await self._send_telegram_message(chat_id, f"Failed to validate LLM output: {e}. Please try again with different content or style.")
            return

        # 5. Prepare for Google Sheets
        processed_content = ProcessedContent(
            user_id=user_id,
            submission_timestamp=submission_timestamp,
            content_type=ingested_content.content_type,
            source_identifier=ingested_content.source_identifier,
            style_hash=style_hash,
            llm_output=llm_output
        )

        row_data = [
            processed_content.source_identifier,
            processed_content.submission_timestamp,
            processed_content.content_type.value,
            processed_content.llm_output.title,
            processed_content.llm_output.rationale,
            processed_content.llm_output.category,
            processed_content.llm_output.variants.x_post,
            processed_content.llm_output.variants.linkedin_post,
        ]

        # 6. Write to Google Sheets
        try:
            await self.google_sheets_client.append_row(row_data)
            await self._send_telegram_message(chat_id, "Content successfully processed and saved to Google Sheets!")
            logger.info(f"Content for user {user_id}, source {ingested_content.source_identifier} successfully written to Google Sheets.")
        except GoogleSheetsError as e:
            logger.error(f"Failed to write to Google Sheets for user {user_id}, source {ingested_content.source_identifier}: {e}")
            await self._send_telegram_message(chat_id, f"Failed to save content to Google Sheets: {e}. Please check bot configuration.")
            # If Sheets write fails, we should ideally remove the generation key from idempotency store
            # to allow retry, but for simplicity and to avoid complex rollback, we log and inform user.
            # A more robust system might use a message queue for Sheets writes.

    async def process_plain_text(self, user_id: int, chat_id: int, text_content: str) -> None:
        """Processes plain text content from Telegram."""
        try:
            ingested_content = await self.content_service.ingest_plain_text(text_content)
            await self._process_content_pipeline(user_id, chat_id, ingested_content)
        except ContentServiceError as e:
            await self._send_telegram_message(chat_id, f"Failed to process plain text: {e}")
            logger.error(f"Plain text processing failed for user {user_id}: {e}")
        except Exception as e:
            await self._send_telegram_message(chat_id, "An unexpected error occurred during text processing.")
            logger.critical(f"Unhandled error during plain text processing for user {user_id}: {e}", exc_info=True)

    async def process_url(self, user_id: int, chat_id: int, url: str) -> None:
        """Processes URL content from Telegram."""
        try:
            ingested_content = await self.content_service.ingest_url(url)
            await self._process_content_pipeline(user_id, chat_id, ingested_content)
        except ContentServiceError as e:
            await self._send_telegram_message(chat_id, f"Failed to process URL: {e}")
            logger.error(f"URL processing failed for user {user_id}, URL {url}: {e}")
        except Exception as e:
            await self._send_telegram_message(chat_id, "An unexpected error occurred during URL processing.")
            logger.critical(f"Unhandled error during URL processing for user {user_id}, URL {url}: {e}", exc_info=True)

    async def process_pdf(self, user_id: int, chat_id: int, document: Document) -> None:
        """Processes PDF document content from Telegram."""
        try:
            ingested_content = await self.content_service.ingest_pdf(document)
            await self._process_content_pipeline(user_id, chat_id, ingested_content)
        except ContentServiceError as e:
            await self._send_telegram_message(chat_id, f"Failed to process PDF: {e}")
            logger.error(f"PDF processing failed for user {user_id}, file {document.file_name}: {e}")
        except Exception as e:
            await self._send_telegram_message(chat_id, "An unexpected error occurred during PDF processing.")
            logger.critical(f"Unhandled error during PDF processing for user {user_id}, file {document.file_name}: {e}", exc_info=True)
