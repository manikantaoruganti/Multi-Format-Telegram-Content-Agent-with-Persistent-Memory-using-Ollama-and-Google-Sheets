import aiosqlite
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class IdempotencyStore:
    """Manages persistent storage for processed generation keys to ensure idempotency."""
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def record_generation(self, generation_key: str, user_id: int, source_identifier: str, style_hash: str) -> None:
        """
        Records a new generation key.
        """
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.now().isoformat()
            await db.execute(
                "INSERT INTO processed_generations (generation_key, user_id, source_identifier, style_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                (generation_key, user_id, source_identifier, style_hash, now)
            )
            await db.commit()
            logger.debug(f"Recorded generation key: {generation_key}")

    async def check_generation_exists(self, generation_key: str) -> bool:
        """
        Checks if a generation key already exists.
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT 1 FROM processed_generations WHERE generation_key = ?", (generation_key,))
            row = await cursor.fetchone()
            await cursor.close()
            exists = bool(row)
            logger.debug(f"Generation key {generation_key} exists: {exists}")
            return exists
