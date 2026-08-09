import logging
from telegram import Document
from app.extractors.text_extractor import TextExtractor
from app.extractors.url_extractor import URLExtractor, URLExtractionError
from app.extractors.pdf_extractor import PDFExtractor, PDFExtractionError
from app.models.content import IngestedContent

logger = logging.getLogger(__name__)

class ContentServiceError(Exception):
    """Custom exception for content service failures."""
    pass

class ContentService:
    """
    Orchestrates content extraction based on type (text, URL, PDF).
    """
    def __init__(self, text_extractor: TextExtractor, url_extractor: URLExtractor, pdf_extractor: PDFExtractor):
        self.text_extractor = text_extractor
        self.url_extractor = url_extractor
        self.pdf_extractor = pdf_extractor

    async def ingest_plain_text(self, text_content: str) -> IngestedContent:
        """Ingests and processes plain text content."""
        try:
            extracted_text, source_identifier = self.text_extractor.extract(text_content)
            logger.info(f"Plain text ingested. Identifier: {source_identifier}")
            return IngestedContent(
                content_type="text",
                extracted_content=extracted_text,
                source_identifier=source_identifier
            )
        except ValueError as e:
            logger.warning(f"Plain text ingestion failed: {e}")
            raise ContentServiceError(f"Invalid plain text: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during plain text ingestion: {e}", exc_info=True)
            raise ContentServiceError(f"Failed to ingest plain text: {e}") from e

    async def ingest_url(self, url: str) -> IngestedContent:
        """Ingests and processes content from a URL."""
        try:
            extracted_text, source_identifier = await self.url_extractor.extract(url)
            logger.info(f"URL content ingested from {url}. Identifier: {source_identifier}")
            return IngestedContent(
                content_type="url",
                extracted_content=extracted_text,
                source_identifier=source_identifier
            )
        except URLExtractionError as e:
            logger.warning(f"URL ingestion failed for {url}: {e}")
            raise ContentServiceError(f"Failed to extract content from URL: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during URL ingestion for {url}: {e}", exc_info=True)
            raise ContentServiceError(f"Failed to ingest URL content: {e}") from e

    async def ingest_pdf(self, document: Document) -> IngestedContent:
        """Ingests and processes content from a PDF document."""
        try:
            extracted_text, source_identifier = await self.pdf_extractor.extract(document)
            logger.info(f"PDF content ingested from {document.file_name}. Identifier: {source_identifier}")
            return IngestedContent(
                content_type="pdf",
                extracted_content=extracted_text,
                source_identifier=source_identifier
            )
        except PDFExtractionError as e:
            logger.warning(f"PDF ingestion failed for {document.file_name}: {e}")
            raise ContentServiceError(f"Failed to extract content from PDF: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during PDF ingestion for {document.file_name}: {e}", exc_info=True)
            raise ContentServiceError(f"Failed to ingest PDF content: {e}") from e
