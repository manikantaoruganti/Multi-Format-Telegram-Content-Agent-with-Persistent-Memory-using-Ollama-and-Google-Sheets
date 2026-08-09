import logging
import ollama
from ollama import AsyncClient
from app.config.settings import Settings
from app.utils.retry import retry_async

logger = logging.getLogger(__name__)

class LLMClientError(Exception):
    """Custom exception for LLM client errors."""
    pass

class OllamaClient:
    """
    Client for interacting with the Ollama LLM API.
    Supports generating responses in JSON format.
    """
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = AsyncClient(host=settings.OLLAMA_BASE_URL)
        self.model = settings.OLLAMA_MODEL
        self.timeout = settings.LLM_TIMEOUT_SECONDS

    @retry_async(max_retries_key="MAX_RETRIES", delay_key="RETRY_DELAY_SECONDS", logger=logger,
                 retry_exceptions=(ollama.ResponseError, ConnectionRefusedError, TimeoutError))
    async def generate_content(self, system_prompt: str, user_prompt: str, format_json: bool = True) -> str:
        """
        Generates content using the configured Ollama model.

        Args:
            system_prompt: The system-level instructions for the LLM.
            user_prompt: The user's specific request or content to process.
            format_json: If True, requests JSON output from the LLM.

        Returns:
            The raw string response from the LLM.

        Raises:
            LLMClientError: If the LLM API call fails or times out.
        """
        try:
            options = {"temperature": 0.7} # Default temperature
            if format_json:
                options["format"] = "json"

            logger.debug(f"Sending request to Ollama model: {self.model}")
            response = await self.client.chat(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                options=options,
                stream=False,
                keep_alive=self.timeout # Keep connection alive for timeout duration
            )
            
            if not response or 'message' not in response or 'content' not in response['message']:
                raise LLMClientError("Invalid response structure from Ollama.")

            content = response['message']['content']
            logger.debug(f"Received response from Ollama (first 100 chars): {content[:100]}...")
            return content
        except ollama.ResponseError as e:
            logger.error(f"Ollama API error: {e}")
            raise LLMClientError(f"Ollama API error: {e}") from e
        except ConnectionRefusedError as e:
            logger.error(f"Connection to Ollama refused. Is Ollama running at {self.settings.OLLAMA_BASE_URL}?")
            raise LLMClientError(f"Connection to Ollama refused: {e}") from e
        except TimeoutError as e:
            logger.error(f"Ollama API call timed out after {self.timeout} seconds.")
            raise LLMClientError(f"Ollama API call timed out: {e}") from e
        except Exception as e:
            logger.error(f"An unexpected error occurred during Ollama API call: {e}", exc_info=True)
            raise LLMClientError(f"Unexpected Ollama error: {e}") from e
