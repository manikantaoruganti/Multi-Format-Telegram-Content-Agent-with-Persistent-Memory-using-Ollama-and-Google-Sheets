import aiosqlite
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class StyleMemory:
    """Manages persistent storage for user-specific writing styles."""
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def set_style(self, user_id: int, style_prompt: str) -> None:
        """
        Sets or updates the writing style for a given user.
        """
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.now().isoformat()
            await db.execute(
                "INSERT OR REPLACE INTO user_styles (user_id, style_prompt, updated_at) VALUES (?, ?, ?)",
                (user_id, style_prompt, now)
            )
            await db.commit()
            logger.debug(f"Style set for user {user_id}: {style_prompt[:50]}...")

    async def get_style(self, user_id: int) -> str | None:
        """
        Retrieves the writing style for a given user.
        Returns None if no style is found.
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT style_prompt FROM user_styles WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            await cursor.close()
            style = row[0] if row else None
            logger.debug(f"Retrieved style for user {user_id}: {style[:50] if style else 'None'}")
            return style
