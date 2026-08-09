import logging
from app.database.idempotency_store import IdempotencyStore
from app.database.style_memory import StyleMemory
from app.utils.hashing import generate_sha256

logger = logging.getLogger(__name__)

class IdempotencyService:
    """
    Manages idempotency for content generation requests.
    A generation is considered unique based on user_id, source_identifier, and style_hash.
    """
    def __init__(self, idempotency_store: IdempotencyStore, style_memory: StyleMemory):
        self.idempotency_store = idempotency_store
        self.style_memory = style_memory

    async def _get_style_hash(self, user_id: int) -> str:
        """Retrieves the user's current style and returns its SHA256 hash."""
        style_prompt = await self.style_memory.get_style(user_id)
        # If no style is set, use a default string to ensure a consistent hash
        return generate_sha256(style_prompt if style_prompt else "default_style_no_style_set")

    async def generate_generation_key(self, user_id: int, source_identifier: str) -> tuple[str, str]:
        """
        Generates a unique generation key based on user ID, source identifier, and current style hash.
        Returns the generation key and the style hash.
        """
        style_hash = await self._get_style_hash(user_id)
        # Combine user_id, source_identifier, and style_hash to form the unique generation identity
        generation_identity_string = f"{user_id}-{source_identifier}-{style_hash}"
        generation_key = generate_sha256(generation_identity_string)
        logger.debug(f"Generated generation key: {generation_key} for user {user_id}, source {source_identifier}, style_hash {style_hash}")
        return generation_key, style_hash

    async def check_and_record_generation(self, generation_key: str, user_id: int, source_identifier: str, style_hash: str) -> bool:
        """
        Checks if a generation key already exists. If not, records it.
        Returns True if a new generation was recorded (i.e., not a duplicate), False otherwise.
        """
        if await self.idempotency_store.check_generation_exists(generation_key):
            logger.info(f"Duplicate generation detected for key: {generation_key}. Skipping processing.")
            return False
        else:
            await self.idempotency_store.record_generation(generation_key, user_id, source_identifier, style_hash)
            logger.info(f"New generation recorded for key: {generation_key}.")
            return True
