import pytest
import aiosqlite
from app.database.style_memory import StyleMemory

@pytest.fixture
async def in_memory_db():
    """Fixture for an in-memory SQLite database for testing."""
    async with aiosqlite.connect(":memory:") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_styles (
                user_id INTEGER PRIMARY KEY,
                style_prompt TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.commit()
        yield db

@pytest.fixture
def style_memory(in_memory_db):
    return StyleMemory(":memory:") # Path doesn't matter for in-memory fixture

@pytest.mark.asyncio
async def test_set_and_get_style(style_memory):
    user_id = 123
    style = "witty and informal"

    await style_memory.set_style(user_id, style)
    retrieved_style = await style_memory.get_style(user_id)

    assert retrieved_style == style

@pytest.mark.asyncio
async def test_get_style_non_existent_user(style_memory):
    user_id = 999
    retrieved_style = await style_memory.get_style(user_id)
    assert retrieved_style is None

@pytest.mark.asyncio
async def test_update_style(style_memory):
    user_id = 456
    initial_style = "formal and academic"
    updated_style = "casual and friendly"

    await style_memory.set_style(user_id, initial_style)
    await style_memory.set_style(user_id, updated_style) # Update
    retrieved_style = await style_memory.get_style(user_id)

    assert retrieved_style == updated_style

@pytest.mark.asyncio
async def test_multiple_users_styles(style_memory):
    user_id1 = 789
    style1 = "poetic"
    user_id2 = 101
    style2 = "technical"

    await style_memory.set_style(user_id1, style1)
    await style_memory.set_style(user_id2, style2)

    retrieved_style1 = await style_memory.get_style(user_id1)
    retrieved_style2 = await style_memory.get_style(user_id2)

    assert retrieved_style1 == style1
    assert retrieved_style2 == style2

@pytest.mark.asyncio
async def test_style_persistence_across_restarts(in_memory_db):
    # Simulate first run
    style_memory1 = StyleMemory(":memory:")
    user_id = 111
    style = "bold and assertive"
    await style_memory1.set_style(user_id, style)
    
    # Simulate restart (new instance of StyleMemory, same underlying DB)
    style_memory2 = StyleMemory(":memory:")
    retrieved_style = await style_memory2.get_style(user_id)
    
    assert retrieved_style == style
