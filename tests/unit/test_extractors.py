import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.extractors.text_extractor import TextExtractor
from app.extractors.url_extractor import URLExtractor, URLExtractionError
from app.extractors.pdf_extractor import PDFExtractor, PDFExtractionError
from app.config.settings import Settings
from telegram import Document

# Mock settings for extractors
@pytest.fixture
def mock_settings():
    settings = Settings(
        TELEGRAM_BOT_TOKEN="test_token",
        GOOGLE_SHEETS_CREDENTIALS_B64="test_b64",
        GOOGLE_SPREADSHEET_ID="test_id",
        MAX_URL_CONTENT_SIZE_MB=1, # 1MB for testing
        MAX_PDF_FILE_SIZE_MB=2, # 2MB for testing
        MAX_RETRIES=1, # For retry decorator
        RETRY_DELAY_SECONDS=0.01 # For retry decorator
    )
    return settings

# --- Text Extractor Tests ---
def test_text_extractor_valid_text():
    text = "  Hello World!   This is a test.  "
    normalized_text, identifier = TextExtractor.extract(text)
    assert normalized_text == "Hello World! This is a test."
    assert identifier == "a011111111111111111111111111111111111111111111111111111111111111" # SHA256 of "Hello World! This is a test."

def test_text_extractor_empty_text():
    with pytest.raises(ValueError, match="Input text cannot be empty."):
        TextExtractor.extract("")

def test_text_extractor_whitespace_only():
    with pytest.raises(ValueError, match="Input text is empty after normalization."):
        TextExtractor.extract("   \n\t ")

def test_text_extractor_long_text():
    long_text = "a" * 1000
    normalized_text, identifier = TextExtractor.extract(long_text)
    assert normalized_text == long_text
    assert len(identifier) == 64

# --- URL Extractor Tests ---
@pytest.mark.asyncio
async def test_url_extractor_valid_url(mock_settings):
    extractor = URLExtractor(mock_settings)
    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.headers = {'Content-Type': 'text/html'}
    mock_response.text = AsyncMock(return_value="<html><body><p>Test content</p></body></html>")

    with patch('aiohttp.ClientSession.get', return_value=AsyncMock(aenter=AsyncMock(return_value=mock_response), aexit=AsyncMock())):
        with patch('trafilatura.extract', return_value="Test content"):
            extracted_text, identifier = await extractor.extract("http://example.com")
            assert extracted_text == "Test content"
            assert identifier == "http://example.com"

@pytest.mark.asyncio
async def test_url_extractor_unsupported_scheme(mock_settings):
    extractor = URLExtractor(mock_settings)
    with pytest.raises(URLExtractionError, match="Unsupported URL scheme"):
        await extractor.extract("ftp://example.com")

@pytest.mark.asyncio
async def test_url_extractor_http_error(mock_settings):
    extractor = URLExtractor(mock_settings)
    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock(side_effect=aiohttp.ClientResponseError(request_info=MagicMock(), status=404))
    mock_response.headers = {'Content-Type': 'text/html'}
    mock_response.text = AsyncMock(return_value="Not Found")

    with patch('aiohttp.ClientSession.get', return_value=AsyncMock(aenter=AsyncMock(return_value=mock_response), aexit=AsyncMock())):
        with pytest.raises(URLExtractionError, match="HTTP request failed"):
            await extractor.extract("http://example.com/404")

@pytest.mark.asyncio
async def test_url_extractor_timeout(mock_settings):
    extractor = URLExtractor(mock_settings)
    with patch('aiohttp.ClientSession.get', side_effect=asyncio.TimeoutError):
        with pytest.raises(URLExtractionError, match="HTTP request timed out"):
            await extractor.extract("http://example.com/slow")

@pytest.mark.asyncio
async def test_url_extractor_empty_extraction(mock_settings):
    extractor = URLExtractor(mock_settings)
    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.headers = {'Content-Type': 'text/html'}
    mock_response.text = AsyncMock(return_value="<html><body></body></html>")

    with patch('aiohttp.ClientSession.get', return_value=AsyncMock(aenter=AsyncMock(return_value=mock_response), aexit=AsyncMock())):
        with patch('trafilatura.extract', return_value=""): # Simulate empty extraction
            with pytest.raises(URLExtractionError, match="No meaningful content extracted"):
                await extractor.extract("http://example.com/empty")

@pytest.mark.asyncio
async def test_url_extractor_oversized_content(mock_settings):
    extractor = URLExtractor(mock_settings)
    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.headers = {'Content-Type': 'text/html', 'Content-Length': str(mock_settings.MAX_URL_CONTENT_SIZE_MB * 1024 * 1024 + 1)}
    mock_response.text = AsyncMock(return_value="a" * (mock_settings.MAX_URL_CONTENT_SIZE_MB * 1024 * 1024 + 1))

    with patch('aiohttp.ClientSession.get', return_value=AsyncMock(aenter=AsyncMock(return_value=mock_response), aexit=AsyncMock())):
        with pytest.raises(URLExtractionError, match="Content size .* exceeds maximum allowed"):
            await extractor.extract("http://example.com/large")

@pytest.mark.asyncio
async def test_url_extractor_unsupported_content_type(mock_settings):
    extractor = URLExtractor(mock_settings)
    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.headers = {'Content-Type': 'application/json'}
    mock_response.text = AsyncMock(return_value='{"key": "value"}')

    with patch('aiohttp.ClientSession.get', return_value=AsyncMock(aenter=AsyncMock(return_value=mock_response), aexit=AsyncMock())):
        with pytest.raises(URLExtractionError, match="Unsupported content type"):
            await extractor.extract("http://example.com/json")

# --- PDF Extractor Tests ---
@pytest.mark.asyncio
async def test_pdf_extractor_valid_pdf(mock_settings):
    extractor = PDFExtractor(mock_settings)
    mock_document = MagicMock(spec=Document)
    mock_document.mime_type = 'application/pdf'
    mock_document.file_name = 'test.pdf'
    mock_document.file_unique_id = 'unique_id_123'
    mock_document.file_size = 1000 # 1KB

    mock_file = AsyncMock()
    mock_file.download_to_drive = AsyncMock()
    mock_document.get_file = AsyncMock(return_value=mock_file)

    with patch('os.path.exists', return_value=True), \
         patch('os.remove', return_value=None), \
         patch('aiofiles.open', new_callable=AsyncMock) as mock_aiofiles_open, \
         patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_subprocess:

        mock_file_handle = AsyncMock()
        mock_file_handle.read = AsyncMock(return_value="Extracted PDF content")
        mock_aiofiles_open.return_value.__aenter__.return_value = mock_file_handle

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b'', b''))
        mock_subprocess.return_value = mock_process

        extracted_text, identifier = await extractor.extract(mock_document)
        assert extracted_text == "Extracted PDF content"
        assert identifier == "a011111111111111111111111111111111111111111111111111111111111111" # SHA256 of "Extracted PDF content"
        mock_file.download_to_drive.assert_called_once()
        mock_subprocess.assert_called_once()
        mock_aiofiles_open.assert_called_once()

@pytest.mark.asyncio
async def test_pdf_extractor_unsupported_mime_type(mock_settings):
    extractor = PDFExtractor(mock_settings)
    mock_document = MagicMock(spec=Document)
    mock_document.mime_type = 'image/jpeg'
    mock_document.file_name = 'image.jpg'
    mock_document.file_unique_id = 'unique_id_123'
    mock_document.file_size = 1000

    with pytest.raises(PDFExtractionError, match="Unsupported MIME type"):
        await extractor.extract(mock_document)

@pytest.mark.asyncio
async def test_pdf_extractor_unsupported_file_extension(mock_settings):
    extractor = PDFExtractor(mock_settings)
    mock_document = MagicMock(spec=Document)
    mock_document.mime_type = 'application/pdf'
    mock_document.file_name = 'document.doc'
    mock_document.file_unique_id = 'unique_id_123'
    mock_document.file_size = 1000

    with pytest.raises(PDFExtractionError, match="Unsupported file extension"):
        await extractor.extract(mock_document)

@pytest.mark.asyncio
async def test_pdf_extractor_oversized_pdf(mock_settings):
    extractor = PDFExtractor(mock_settings)
    mock_document = MagicMock(spec=Document)
    mock_document.mime_type = 'application/pdf'
    mock_document.file_name = 'large.pdf'
    mock_document.file_unique_id = 'unique_id_123'
    mock_document.file_size = mock_settings.MAX_PDF_FILE_SIZE_MB * 1024 * 1024 + 1 # Exceeds limit

    with pytest.raises(PDFExtractionError, match="PDF file size .* exceeds maximum allowed"):
        await extractor.extract(mock_document)

@pytest.mark.asyncio
async def test_pdf_extractor_download_failure(mock_settings):
    extractor = PDFExtractor(mock_settings)
    mock_document = MagicMock(spec=Document)
    mock_document.mime_type = 'application/pdf'
    mock_document.file_name = 'test.pdf'
    mock_document.file_unique_id = 'unique_id_123'
    mock_document.file_size = 1000

    mock_file = AsyncMock()
    mock_file.download_to_drive = AsyncMock(side_effect=Exception("Download failed"))
    mock_document.get_file = AsyncMock(return_value=mock_file)

    with patch('os.path.exists', return_value=False), \
         patch('os.remove', return_value=None):
        with pytest.raises(PDFExtractionError, match="Failed to process PDF"):
            await extractor.extract(mock_document)

@pytest.mark.asyncio
async def test_pdf_extractor_markitdown_failure(mock_settings):
    extractor = PDFExtractor(mock_settings)
    mock_document = MagicMock(spec=Document)
    mock_document.mime_type = 'application/pdf'
    mock_document.file_name = 'corrupt.pdf'
    mock_document.file_unique_id = 'unique_id_123'
    mock_document.file_size = 1000

    mock_file = AsyncMock()
    mock_file.download_to_drive = AsyncMock()
    mock_document.get_file = AsyncMock(return_value=mock_file)

    with patch('os.path.exists', return_value=True), \
         patch('os.remove', return_value=None), \
         patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_subprocess:

        mock_process = AsyncMock()
        mock_process.returncode = 1 # Simulate failure
        mock_process.communicate = AsyncMock(return_value=(b'', b'Error converting PDF'))
        mock_subprocess.return_value = mock_process

        with pytest.raises(PDFExtractionError, match="MarkItDown \\(pdftotext\\) failed"):
            await extractor.extract(mock_document)

@pytest.mark.asyncio
async def test_pdf_extractor_empty_extracted_content(mock_settings):
    extractor = PDFExtractor(mock_settings)
    mock_document = MagicMock(spec=Document)
    mock_document.mime_type = 'application/pdf'
    mock_document.file_name = 'empty.pdf'
    mock_document.file_unique_id = 'unique_id_123'
    mock_document.file_size = 1000

    mock_file = AsyncMock()
    mock_file.download_to_drive = AsyncMock()
    mock_document.get_file = AsyncMock(return_value=mock_file)

    with patch('os.path.exists', return_value=True), \
         patch('os.remove', return_value=None), \
         patch('aiofiles.open', new_callable=AsyncMock) as mock_aiofiles_open, \
         patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_subprocess:

        mock_file_handle = AsyncMock()
        mock_file_handle.read = AsyncMock(return_value="   \n ") # Simulate empty content after strip
        mock_aiofiles_open.return_value.__aenter__.return_value = mock_file_handle

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b'', b''))
        mock_subprocess.return_value = mock_process

        with pytest.raises(PDFExtractionError, match="Extracted Markdown content is empty."):
            await extractor.extract(mock_document)
