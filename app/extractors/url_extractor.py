import logging
import aiohttp
import trafilatura
from urllib.parse import urlparse
from app.utils.hashing import generate_sha256
from app.utils.retry import retry_async
from app.config.settings import Settings

logger = logging.getLogger(__name__)

class URLExtractionError(Exception):
    """Custom exception for URL extraction failures."""
    pass

class URLExtractor:
    """Extracts main article content from a given URL using Trafilatura."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.max_content_size_bytes = settings.MAX_URL_CONTENT_SIZE_MB * 1024 * 1024

    @retry_async(max_retries_key="MAX_RETRIES", delay_key="RETRY_DELAY_SECONDS", logger=logger)
    async def _fetch_url_content(self, session: aiohttp.ClientSession, url: str) -> str:
        """Fetches raw HTML content from a URL with validation and size limits."""
        parsed_url = urlparse(url)
        if parsed_url.scheme not in ['http', 'https']:
            raise URLExtractionError(f"Unsupported URL scheme: {parsed_url.scheme}. Only http/https are allowed.")

        try:
            async with session.get(url, timeout=30, allow_redirects=True) as response:
                response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

                content_type = response.headers.get('Content-Type', '').lower()
                if not any(ct in content_type for ct in ['text/html', 'application/xhtml+xml']):
                    raise URLExtractionError(f"Unsupported content type: {content_type}. Expected HTML.")

                # Check content length header if available
                content_length = response.headers.get('Content-Length')
                if content_length and int(content_length) > self.max_content_size_bytes:
                    raise URLExtractionError(f"Content size ({int(content_length)/1024/1024:.2f}MB) exceeds maximum allowed ({self.settings.MAX_URL_CONTENT_SIZE_MB}MB).")

                # Read content with size limit
                content = await response.text(limit=self.max_content_size_bytes)
                if len(content.encode('utf-8')) > self.max_content_size_bytes:
                    raise URLExtractionError(f"Downloaded content size exceeds maximum allowed ({self.settings.MAX_URL_CONTENT_SIZE_MB}MB).")

                return content
        except aiohttp.ClientError as e:
            raise URLExtractionError(f"HTTP request failed for {url}: {e}") from e
        except asyncio.TimeoutError:
            raise URLExtractionError(f"HTTP request timed out for {url}")
        except Exception as e:
            raise URLExtractionError(f"An unexpected error occurred while fetching {url}: {e}") from e

    async def extract(self, url: str) -> tuple[str, str]:
        """
        Extracts the main article text from a URL.

        Args:
            url: The URL to extract content from.

        Returns:
            A tuple containing the extracted article text and the original URL as source identifier.

        Raises:
            URLExtractionError: If extraction fails at any stage.
        """
        async with aiohttp.ClientSession() as session:
            html_content = await self._fetch_url_content(session, url)

        extracted_text = trafilatura.extract(html_content, include_comments=False, include_tables=False)

        if not extracted_text or not extracted_text.strip():
            raise URLExtractionError(f"No meaningful content extracted from URL: {url}")

        logger.debug(f"Content extracted from URL: {url}. Length: {len(extracted_text)} chars.")
        return extracted_text, url
