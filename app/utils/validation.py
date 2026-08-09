import re
from urllib.parse import urlparse

def is_valid_url(text: str) -> bool:
    """
    Checks if the given text is a valid HTTP/HTTPS URL.
    """
    try:
        result = urlparse(text)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except ValueError:
        return False

def is_x_post_valid(text: str) -> bool:
    """
    Checks if an X (Twitter) post is valid (non-empty and <= 280 characters).
    """
    return bool(text.strip()) and len(text) <= 280
