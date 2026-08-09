import asyncio
import logging
from functools import wraps
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

def retry_async(max_retries_key: str, delay_key: str, logger: logging.Logger, retry_exceptions: tuple = (Exception,)) -> callable:
    """
    A decorator for asynchronous functions to implement exponential backoff and retry logic.
    Configuration for max retries and initial delay is fetched from settings.

    Args:
        max_retries_key: The key in settings for maximum retry attempts.
        delay_key: The key in settings for initial retry delay in seconds.
        logger: The logger instance to use for logging retry attempts.
        retry_exceptions: A tuple of exception types to retry on.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Dynamically import settings to avoid circular dependencies
            from app.config.settings import get_settings
            settings = get_settings()

            max_retries = getattr(settings, max_retries_key, 3)
            initial_delay = getattr(settings, delay_key, 2)

            @retry(
                wait=wait_exponential(multiplier=1, min=initial_delay, max=60),
                stop=stop_after_attempt(max_retries + 1), # +1 for the initial attempt
                retry=retry_if_exception_type(retry_exceptions),
                reraise=True,
                before_sleep=lambda retry_state: logger.warning(
                    f"Retrying {retry_state.fn.__name__} (attempt {retry_state.attempt_number}/{max_retries + 1}) "
                    f"after {retry_state.outcome.exception.__class__.__name__}: {retry_state.outcome.exception}"
                )
            )
            async def _retry_func():
                return await func(*args, **kwargs)

            return await _retry_func()
        return wrapper
    return decorator
