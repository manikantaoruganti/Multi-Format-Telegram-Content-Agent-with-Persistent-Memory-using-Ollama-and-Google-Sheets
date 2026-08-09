import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram import Update, Message, Document
from app.bot.handlers import message_handler
from app.services.ingestion_service import IngestionService
from app.utils.validation import is_valid_url

# Mock IngestionService for testing handlers
@pytest.fixture
def mock_ingestion_service():
    service = MagicMock(spec=IngestionService)
    service.process_plain_text = AsyncMock()
    service.process_url = AsyncMock()
    service.process_pdf = AsyncMock()
    return service

@pytest.fixture
def mock_context(mock_ingestion_service):
    context = MagicMock()
    context.bot_data = {'ingestion_service': mock_ingestion_service}
    context.bot = AsyncMock() # Mock bot for sending messages
    return context

@pytest.mark.asyncio
async def test_message_handler_plain_text(mock_ingestion_service, mock_context):
    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    update.message.text = "This is a plain text message."
    update.message.document = None
    update.effective_user.id = 123
    update.effective_chat.id = 456
    update.message.reply_text = AsyncMock()

    await message_handler(update, mock_context)

    mock_ingestion_service.process_plain_text.assert_called_once_with(123, 456, "This is a plain text message.")
    mock_ingestion_service.process_url.assert_not_called()
    mock_ingestion_service.process_pdf.assert_not_called()
    update.message.reply_text.assert_called_once_with("Received text. Analyzing...")

@pytest.mark.asyncio
async def test_message_handler_url(mock_ingestion_service, mock_context):
    url = "https://www.example.com/article"
    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    update.message.text = url
    update.message.document = None
    update.effective_user.id = 123
    update.effective_chat.id = 456
    update.message.reply_text = AsyncMock()

    await message_handler(update, mock_context)

    mock_ingestion_service.process_url.assert_called_once_with(123, 456, url)
    mock_ingestion_service.process_plain_text.assert_not_called()
    mock_ingestion_service.process_pdf.assert_not_called()
    update.message.reply_text.assert_called_once_with("Received URL. Fetching content...")

@pytest.mark.asyncio
async def test_message_handler_pdf(mock_ingestion_service, mock_context):
    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    update.message.text = None
    update.message.document = MagicMock(spec=Document)
    update.message.document.mime_type = 'application/pdf'
    update.effective_user.id = 123
    update.effective_chat.id = 456
    update.message.reply_text = AsyncMock()

    await message_handler(update, mock_context)

    mock_ingestion_service.process_pdf.assert_called_once_with(123, 456, update.message.document)
    mock_ingestion_service.process_plain_text.assert_not_called()
    mock_ingestion_service.process_url.assert_not_called()
    update.message.reply_text.assert_called_once_with("Received PDF. Processing...")

@pytest.mark.asyncio
async def test_message_handler_unsupported_document(mock_ingestion_service, mock_context):
    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    update.message.text = None
    update.message.document = MagicMock(spec=Document)
    update.message.document.mime_type = 'image/jpeg' # Unsupported
    update.effective_user.id = 123
    update.effective_chat.id = 456
    update.message.reply_text = AsyncMock()

    await message_handler(update, mock_context)

    mock_ingestion_service.process_plain_text.assert_not_called()
    mock_ingestion_service.process_url.assert_not_called()
    mock_ingestion_service.process_pdf.assert_not_called()
    update.message.reply_text.assert_called_once_with("Unsupported message type. Please send text, a URL, or a PDF document.")

@pytest.mark.asyncio
async def test_message_handler_empty_text(mock_ingestion_service, mock_context):
    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    update.message.text = "   " # Empty after strip
    update.message.document = None
    update.effective_user.id = 123
    update.effective_chat.id = 456
    update.message.reply_text = AsyncMock()

    await message_handler(update, mock_context)

    mock_ingestion_service.process_plain_text.assert_not_called()
    mock_ingestion_service.process_url.assert_not_called()
    mock_ingestion_service.process_pdf.assert_not_called()
    update.message.reply_text.assert_called_once_with("Please send some text, a URL, or a PDF document.")

@pytest.mark.asyncio
async def test_message_handler_ingestion_service_error(mock_ingestion_service, mock_context):
    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    update.message.text = "Error text"
    update.message.document = None
    update.effective_user.id = 123
    update.effective_chat.id = 456
    update.message.reply_text = AsyncMock()

    mock_ingestion_service.process_plain_text.side_effect = Exception("Simulated ingestion error")

    await message_handler(update, mock_context)

    mock_ingestion_service.process_plain_text.assert_called_once()
    update.message.reply_text.assert_called_once_with(
        "An unexpected error occurred while processing your request. Please try again later or contact support."
    )

@pytest.mark.asyncio
async def test_message_handler_unknown_command(mock_ingestion_service, mock_context):
    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    update.message.text = "/unknowncommand"
    update.message.document = None
    update.effective_user.id = 123
    update.effective_chat.id = 456
    update.message.reply_text = AsyncMock()

    await message_handler(update, mock_context)

    mock_ingestion_service.process_plain_text.assert_not_called()
    mock_ingestion_service.process_url.assert_not_called()
    mock_ingestion_service.process_pdf.assert_not_called()
    update.message.reply_text.assert_not_called() # Should not reply for unknown commands
