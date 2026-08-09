import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import aiosqlite

from app.config.settings import Settings
from app.services.ingestion_service import IngestionService
from app.services.content_service import ContentService
from app.services.idempotency_service import IdempotencyService
from app.database.style_memory import StyleMemory
from app.database.idempotency_store import IdempotencyStore
from app.extractors.text_extractor import TextExtractor
from app.extractors.url_extractor import URLExtractor, URLExtractionError
from app.extractors.pdf_extractor import PDFExtractor, PDFExtractionError
from app.llm.ollama_client import OllamaClient, LLMClientError
from app.llm.validator import LLMValidator, LLMValidationException
from app.sheets.google_sheets import GoogleSheetsClient, GoogleSheetsError
from app.models.content import LLMContent, ContentVariants, IngestedContent, ProcessedContent
from app.utils.hashing import generate_sha256
from telegram import Document, Update, Message

# --- Fixtures for Mocking Dependencies ---
@pytest.fixture
def mock_settings():
    return Settings(
        TELEGRAM_BOT_TOKEN="test_token",
        GOOGLE_SHEETS_CREDENTIALS_B64="test_b64",
        GOOGLE_SPREADSHEET_ID="test_id",
        GOOGLE_WORKSHEET_NAME="TestContent",
        MAX_RETRIES=1,
        RETRY_DELAY_SECONDS=0.01,
        MAX_URL_CONTENT_SIZE_MB=1,
        MAX_PDF_FILE_SIZE_MB=2,
        LLM_TIMEOUT_SECONDS=10
    )

@pytest.fixture
async def in_memory_db():
    async with aiosqlite.connect(":memory:") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_styles (
                user_id INTEGER PRIMARY KEY,
                style_prompt TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS processed_generations (
                generation_key TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                source_identifier TEXT NOT NULL,
                style_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        await db.commit()
        yield db

@pytest.fixture
def mock_style_memory(in_memory_db):
    return StyleMemory(":memory:")

@pytest.fixture
def mock_idempotency_store(in_memory_db):
    return IdempotencyStore(":memory:")

@pytest.fixture
def mock_idempotency_service(mock_idempotency_store, mock_style_memory):
    return IdempotencyService(mock_idempotency_store, mock_style_memory)

@pytest.fixture
def mock_text_extractor():
    extractor = MagicMock(spec=TextExtractor)
    extractor.extract.return_value = ("Normalized text", "text_sha256")
    return extractor

@pytest.fixture
def mock_url_extractor():
    extractor = MagicMock(spec=URLExtractor)
    extractor.extract = AsyncMock(return_value=("Extracted URL content", "http://example.com/url"))
    return extractor

@pytest.fixture
def mock_pdf_extractor():
    extractor = MagicMock(spec=PDFExtractor)
    extractor.extract = AsyncMock(return_value=("Extracted PDF content", "pdf_sha256"))
    return extractor

@pytest.fixture
def mock_content_service(mock_text_extractor, mock_url_extractor, mock_pdf_extractor):
    return ContentService(mock_text_extractor, mock_url_extractor, mock_pdf_extractor)

@pytest.fixture
def mock_ollama_client():
    client = MagicMock(spec=OllamaClient)
    client.generate_content = AsyncMock()
    return client

@pytest.fixture
def mock_llm_validator(mock_ollama_client):
    validator = MagicMock(spec=LLMValidator)
    validator.validate_and_correct = AsyncMock()
    return validator

@pytest.fixture
def mock_google_sheets_client():
    client = MagicMock(spec=GoogleSheetsClient)
    client.append_row = AsyncMock()
    client._get_worksheet = AsyncMock() # Mock internal method for header check
    return client

@pytest.fixture
def ingestion_service(
    mock_settings,
    mock_content_service,
    mock_style_memory,
    mock_ollama_client,
    mock_llm_validator,
    mock_google_sheets_client,
    mock_idempotency_service
):
    return IngestionService(
        settings=mock_settings,
        content_service=mock_content_service,
        style_memory=mock_style_memory,
        ollama_client=mock_ollama_client,
        llm_validator=mock_llm_validator,
        google_sheets_client=mock_google_sheets_client,
        idempotency_service=mock_idempotency_service
    )

@pytest.fixture
def mock_telegram_context():
    context = MagicMock()
    context.bot = AsyncMock()
    context.bot.send_message = AsyncMock()
    return context

# --- Test Data ---
@pytest.fixture
def sample_llm_output():
    return LLMContent(
        title="Sample Title",
        rationale="Sample Rationale",
        category="Sample Category",
        variants=ContentVariants(
            x_post="Sample X Post (<=280 chars)",
            linkedin_post="Sample LinkedIn Post, which is longer and more professional."
        )
    )

# --- Tests ---
@pytest.mark.asyncio
async def test_ingestion_service_process_plain_text_success(
    ingestion_service,
    mock_content_service,
    mock_style_memory,
    mock_llm_validator,
    mock_google_sheets_client,
    mock_idempotency_service,
    mock_telegram_context,
    sample_llm_output
):
    user_id = 1
    chat_id = 1
    text_content = "Hello world"

    mock_style_memory.get_style.return_value = "witty"
    mock_llm_validator.validate_and_correct.return_value = sample_llm_output
    mock_idempotency_service.check_and_record_generation.return_value = True # Not a duplicate

    with patch.object(ingestion_service, '_send_telegram_message', new=mock_telegram_context.bot.send_message):
        await ingestion_service.process_plain_text(user_id, chat_id, text_content)

    mock_content_service.ingest_plain_text.assert_called_once_with(text_content)
    mock_style_memory.get_style.assert_called_once_with(user_id)
    mock_llm_validator.validate_and_correct.assert_called_once()
    mock_google_sheets_client.append_row.assert_called_once()
    mock_telegram_context.bot.send_message.assert_called_with(chat_id, "Content successfully processed and saved to Google Sheets!")

@pytest.mark.asyncio
async def test_ingestion_service_process_url_success(
    ingestion_service,
    mock_content_service,
    mock_style_memory,
    mock_llm_validator,
    mock_google_sheets_client,
    mock_idempotency_service,
    mock_telegram_context,
    sample_llm_output
):
    user_id = 1
    chat_id = 1
    url = "http://example.com/article"

    mock_style_memory.get_style.return_value = "witty"
    mock_llm_validator.validate_and_correct.return_value = sample_llm_output
    mock_idempotency_service.check_and_record_generation.return_value = True

    with patch.object(ingestion_service, '_send_telegram_message', new=mock_telegram_context.bot.send_message):
        await ingestion_service.process_url(user_id, chat_id, url)

    mock_content_service.ingest_url.assert_called_once_with(url)
    mock_style_memory.get_style.assert_called_once_with(user_id)
    mock_llm_validator.validate_and_correct.assert_called_once()
    mock_google_sheets_client.append_row.assert_called_once()
    mock_telegram_context.bot.send_message.assert_called_with(chat_id, "Content successfully processed and saved to Google Sheets!")

@pytest.mark.asyncio
async def test_ingestion_service_process_pdf_success(
    ingestion_service,
    mock_content_service,
    mock_style_memory,
    mock_llm_validator,
    mock_google_sheets_client,
    mock_idempotency_service,
    mock_telegram_context,
    sample_llm_output
):
    user_id = 1
    chat_id = 1
    mock_document = MagicMock(spec=Document)
    mock_document.file_name = "test.pdf"

    mock_style_memory.get_style.return_value = "witty"
    mock_llm_validator.validate_and_correct.return_value = sample_llm_output
    mock_idempotency_service.check_and_record_generation.return_value = True

    with patch.object(ingestion_service, '_send_telegram_message', new=mock_telegram_context.bot.send_message):
        await ingestion_service.process_pdf(user_id, chat_id, mock_document)

    mock_content_service.ingest_pdf.assert_called_once_with(mock_document)
    mock_style_memory.get_style.assert_called_once_with(user_id)
    mock_llm_validator.validate_and_correct.assert_called_once()
    mock_google_sheets_client.append_row.assert_called_once()
    mock_telegram_context.bot.send_message.assert_called_with(chat_id, "Content successfully processed and saved to Google Sheets!")

@pytest.mark.asyncio
async def test_ingestion_service_content_service_error(
    ingestion_service,
    mock_content_service,
    mock_telegram_context
):
    user_id = 1
    chat_id = 1
    text_content = "Error text"

    mock_content_service.ingest_plain_text.side_effect = ContentServiceError("Extraction failed")

    with patch.object(ingestion_service, '_send_telegram_message', new=mock_telegram_context.bot.send_message):
        await ingestion_service.process_plain_text(user_id, chat_id, text_content)

    mock_telegram_context.bot.send_message.assert_called_with(chat_id, "Failed to process plain text: Extraction failed")
    mock_content_service.ingest_plain_text.assert_called_once()
    # Ensure no further pipeline steps are called
    ingestion_service.style_memory.get_style.assert_not_called()
    ingestion_service.llm_validator.validate_and_correct.assert_not_called()
    ingestion_service.google_sheets_client.append_row.assert_not_called()

@pytest.mark.asyncio
async def test_ingestion_service_llm_generation_error(
    ingestion_service,
    mock_content_service,
    mock_ollama_client,
    mock_telegram_context
):
    user_id = 1
    chat_id = 1
    text_content = "Hello world"

    mock_content_service.ingest_plain_text.return_value = IngestedContent(
        content_type="text", extracted_content="Hello world", source_identifier="test_id"
    )
    ingestion_service.style_memory.get_style.return_value = "witty"
    mock_ollama_client.generate_content.side_effect = LLMClientError("Ollama unavailable")
    mock_idempotency_service.check_and_record_generation.return_value = True

    with patch.object(ingestion_service, '_send_telegram_message', new=mock_telegram_context.bot.send_message):
        await ingestion_service.process_plain_text(user_id, chat_id, text_content)

    mock_telegram_context.bot.send_message.assert_called_with(chat_id, "Failed to generate content with LLM: Ollama unavailable")
    mock_ollama_client.generate_content.assert_called_once()
    # Ensure no further pipeline steps are called
    ingestion_service.llm_validator.validate_and_correct.assert_not_called()
    ingestion_service.google_sheets_client.append_row.assert_not_called()

@pytest.mark.asyncio
async def test_ingestion_service_llm_validation_error(
    ingestion_service,
    mock_content_service,
    mock_ollama_client,
    mock_llm_validator,
    mock_telegram_context
):
    user_id = 1
    chat_id = 1
    text_content = "Hello world"

    mock_content_service.ingest_plain_text.return_value = IngestedContent(
        content_type="text", extracted_content="Hello world", source_identifier="test_id"
    )
    ingestion_service.style_memory.get_style.return_value = "witty"
    mock_ollama_client.generate_content.return_value = "{invalid json}"
    mock_llm_validator.validate_and_correct.side_effect = LLMValidationException("Validation failed")
    mock_idempotency_service.check_and_record_generation.return_value = True

    with patch.object(ingestion_service, '_send_telegram_message', new=mock_telegram_context.bot.send_message):
        await ingestion_service.process_plain_text(user_id, chat_id, text_content)

    mock_telegram_context.bot.send_message.assert_called_with(chat_id, "Failed to validate LLM output: Validation failed. Please try again with different content or style.")
    mock_llm_validator.validate_and_correct.assert_called_once()
    # Ensure no further pipeline steps are called
    ingestion_service.google_sheets_client.append_row.assert_not_called()

@pytest.mark.asyncio
async def test_ingestion_service_google_sheets_error(
    ingestion_service,
    mock_content_service,
    mock_llm_validator,
    mock_google_sheets_client,
    mock_telegram_context,
    sample_llm_output
):
    user_id = 1
    chat_id = 1
    text_content = "Hello world"

    mock_content_service.ingest_plain_text.return_value = IngestedContent(
        content_type="text", extracted_content="Hello world", source_identifier="test_id"
    )
    ingestion_service.style_memory.get_style.return_value = "witty"
    mock_llm_validator.validate_and_correct.return_value = sample_llm_output
    mock_google_sheets_client.append_row.side_effect = GoogleSheetsError("Sheets API error")
    mock_idempotency_service.check_and_record_generation.return_value = True

    with patch.object(ingestion_service, '_send_telegram_message', new=mock_telegram_context.bot.send_message):
        await ingestion_service.process_plain_text(user_id, chat_id, text_content)

    mock_telegram_context.bot.send_message.assert_called_with(chat_id, "Failed to save content to Google Sheets: Sheets API error. Please check bot configuration.")
    mock_google_sheets_client.append_row.assert_called_once()

@pytest.mark.asyncio
async def test_ingestion_service_idempotency_prevents_duplicate(
    ingestion_service,
    mock_content_service,
    mock_idempotency_service,
    mock_telegram_context
):
    user_id = 1
    chat_id = 1
    text_content = "Hello world"

    mock_content_service.ingest_plain_text.return_value = IngestedContent(
        content_type="text", extracted_content="Hello world", source_identifier="test_id"
    )
    mock_idempotency_service.check_and_record_generation.return_value = False # Simulate duplicate

    with patch.object(ingestion_service, '_send_telegram_message', new=mock_telegram_context.bot.send_message):
        await ingestion_service.process_plain_text(user_id, chat_id, text_content)

    mock_idempotency_service.check_and_record_generation.assert_called_once()
    mock_telegram_context.bot.send_message.assert_called_with(chat_id, "This content with your current style has already been processed. No new entry created.")
    # Ensure no further pipeline steps are called
    ingestion_service.style_memory.get_style.assert_not_called()
    ingestion_service.llm_validator.validate_and_correct.assert_not_called()
    ingestion_service.google_sheets_client.append_row.assert_not_called()

@pytest.mark.asyncio
async def test_critical_style_scenario(
    ingestion_service,
    mock_content_service,
    mock_style_memory,
    mock_ollama_client,
    mock_llm_validator,
    mock_google_sheets_client,
    mock_idempotency_service,
    mock_telegram_context
):
    user_id = 100
    chat_id = 100
    url = "http://example.com/critical_article"
    source_identifier = url
    extracted_content = "This is the content of the critical article."

    mock_content_service.ingest_url.return_value = IngestedContent(
        content_type="url", extracted_content=extracted_content, source_identifier=source_identifier
    )

    # --- Scenario 1: Process URL with default style ---
    mock_style_memory.get_style.return_value = None # No style set
    
    # Mock LLM output for default style
    default_llm_output = LLMContent(
        title="Default Title",
        rationale="Default Rationale",
        category="Default Category",
        variants=ContentVariants(x_post="Default X", linkedin_post="Default LinkedIn")
    )
    mock_llm_validator.validate_and_correct.return_value = default_llm_output
    mock_idempotency_service.check_and_record_generation.side_effect = [True, True] # First is new, second will be new too

    with patch.object(ingestion_service, '_send_telegram_message', new=mock_telegram_context.bot.send_message):
        await ingestion_service.process_url(user_id, chat_id, url)

    # Verify first generation
    mock_content_service.ingest_url.assert_called_once_with(url)
    mock_style_memory.get_style.assert_called_once_with(user_id)
    # Check prompt for default style
    args, _ = mock_ollama_client.generate_content.call_args
    assert 'User\'s Preferred Style: "neutral, professional tone"' in args[1]
    mock_llm_validator.validate_and_correct.assert_called_once()
    mock_google_sheets_client.append_row.assert_called_once()
    mock_telegram_context.bot.send_message.assert_called_with(chat_id, "Content successfully processed and saved to Google Sheets!")

    # Reset mocks for second scenario
    mock_content_service.ingest_url.reset_mock()
    mock_style_memory.get_style.reset_mock()
    mock_ollama_client.generate_content.reset_mock()
    mock_llm_validator.validate_and_correct.reset_mock()
    mock_google_sheets_client.append_row.reset_mock()
    mock_telegram_context.bot.send_message.reset_mock()

    # --- Scenario 2: Set style and process SAME URL ---
    custom_style = "All output must be in the form of a haiku."
    await mock_style_memory.set_style(user_id, custom_style)

    # Mock LLM output for haiku style
    haiku_llm_output = LLMContent(
        title="Haiku Title",
        rationale="Haiku Rationale",
        category="Haiku Category",
        variants=ContentVariants(x_post="Haiku X", linkedin_post="Haiku LinkedIn")
    )
    mock_llm_validator.validate_and_correct.return_value = haiku_llm_output

    with patch.object(ingestion_service, '_send_telegram_message', new=mock_telegram_context.bot.send_message):
        await ingestion_service.process_url(user_id, chat_id, url)

    # Verify second generation (new row)
    mock_content_service.ingest_url.assert_called_once_with(url)
    mock_style_memory.get_style.assert_called_once_with(user_id)
    # Check prompt for custom style
    args, _ = mock_ollama_client.generate_content.call_args
    assert f'User\'s Preferred Style: "{custom_style}"' in args[1]
    mock_llm_validator.validate_and_correct.assert_called_once()
    mock_google_sheets_client.append_row.assert_called_once()
    mock_telegram_context.bot.send_message.assert_called_with(chat_id, "Content successfully processed and saved to Google Sheets!")

    # Verify idempotency service was called twice, and both were new generations
    assert mock_idempotency_service.check_and_record_generation.call_count == 2
    # The generation keys should be different because the style hash changed
    call1_args = mock_idempotency_service.generate_generation_key.call_args_list[0]
    call2_args = mock_idempotency_service.generate_generation_key.call_args_list[1]
    assert call1_args[0][0] == user_id
    assert call1_args[0][1] == source_identifier
    assert call2_args[0][0] == user_id
    assert call2_args[0][1] == source_identifier
    # The style hashes should be different
    assert call1_args.await_result()[1] != call2_args.await_result()[1]
    # The generation keys should be different
    assert call1_args.await_result()[0] != call2_args.await_result()[0]

    # Verify LLM outputs were different (implicitly by mock return values)
    assert default_llm_output != haiku_llm_output

@pytest.mark.asyncio
async def test_google_sheets_header_initialization(mock_google_sheets_client, mock_settings):
    # Simulate an empty worksheet
    mock_worksheet = MagicMock()
    mock_worksheet.row_values = AsyncMock(return_value=[]) # No headers
    mock_worksheet.update = AsyncMock()
    mock_google_sheets_client._spreadsheet.worksheet.return_value = mock_worksheet
    mock_google_sheets_client._spreadsheet.add_worksheet.return_value = mock_worksheet # If worksheet not found

    # Call _get_worksheet, which handles initialization
    worksheet = await mock_google_sheets_client._get_worksheet()

    # Assert that headers were updated
    mock_worksheet.update.assert_called_once_with([GoogleSheetsClient.REQUIRED_HEADERS], "A1")
    assert worksheet == mock_worksheet

@pytest.mark.asyncio
async def test_google_sheets_header_already_exists(mock_google_sheets_client, mock_settings):
    # Simulate a worksheet with correct headers
    mock_worksheet = MagicMock()
    mock_worksheet.row_values = AsyncMock(return_value=GoogleSheetsClient.REQUIRED_HEADERS)
    mock_worksheet.update = AsyncMock()
    mock_google_sheets_client._spreadsheet.worksheet.return_value = mock_worksheet

    # Call _get_worksheet
    worksheet = await mock_google_sheets_client._get_worksheet()

    # Assert that headers were NOT updated
    mock_worksheet.update.assert_not_called()
    assert worksheet == mock_worksheet

@pytest.mark.asyncio
async def test_google_sheets_header_incorrect_exists(mock_google_sheets_client, mock_settings):
    # Simulate a worksheet with incorrect headers
    mock_worksheet = MagicMock()
    mock_worksheet.row_values = AsyncMock(return_value=["WrongHeader1", "WrongHeader2"])
    mock_worksheet.update = AsyncMock()
    mock_google_sheets_client._spreadsheet.worksheet.return_value = mock_worksheet

    # Call _get_worksheet
    worksheet = await mock_google_sheets_client._get_worksheet()

    # Assert that headers were updated to the correct ones
    mock_worksheet.update.assert_called_once_with([GoogleSheetsClient.REQUIRED_HEADERS], "A1")
    assert worksheet == mock_worksheet
