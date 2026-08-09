import aiosqlite
import logging

logger = logging.getLogger(__name__)

async def init_db(style_db_path: str, generation_db_path: str) -> None:
    """Initializes the SQLite databases for styles and processed generations."""
    # Initialize style database
    async with aiosqlite.connect(style_db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_styles (
                user_id INTEGER PRIMARY KEY,
                style_prompt TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.commit()
        logger.info(f"SQLite style database initialized at {style_db_path}")

    # Initialize generation database
    async with aiosqlite.connect(generation_db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS processed_generations (
                generation_key TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                source_identifier TEXT NOT NULL,
                style_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        await db.commit()
        logger.info(f"SQLite generation database initialized at {generation_db_path}")
