import logging
import re
from app.utils.hashing import generate_sha256

logger = logging.getLogger(__name__)

class TextExtractor:
    """Extracts and normalizes plain text content."""

    @staticmethod
    def extract(text_content: str) -> tuple[str, str]:
        """
        Normalizes plain text content and generates a source identifier.

        Args:
            text_content: The raw plain text.

        Returns:
            A tuple containing the normalized text and its SHA256 source identifier.

        Raises:
            ValueError: If the input text is empty after normalization.
        """
        if not text_content:
            raise ValueError("Input text cannot be empty.")

        # Normalize whitespace: replace multiple spaces/newlines with a single space, then strip
        normalized_text = re.sub(r'\s+', ' ', text_content).strip()

        if not normalized_text:
            raise ValueError("Input text is empty after normalization.")

        source_identifier = generate_sha256(normalized_text)
        logger.debug(f"Text extracted. Identifier: {source_identifier}")
        return normalized_text, source_identifier
