import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram import Update, Message, Document
from telegram.ext import ContextTypes
from app.bot.handlers import start_command, set_style_command
from app.database.style_memory import StyleMemory
import aiosqlite

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
def mock_style_memory(in_memory_db):
    return StyleMemory(":memory:")

@pytest.fixture
def mock_context(mock_style_memory):
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot_data = {'style_memory': mock_style_memory}
    context.args = [] # Default empty args for commands
    context.bot = AsyncMock() # Mock bot for sending messages
    return context

@pytest.mark.asyncio
async def test_start_command(mock_context):
    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    update.message.reply_text = AsyncMock()
    update.effective_user.id = 123

    await start_command(update, mock_context)

    update.message.reply_text.assert_called_once()
    args, kwargs = update.message.reply_text.call_args
    assert "Welcome to the Content Team Agent." in args[0]
    assert "Send me:" in args[0]
    assert "• plain text" in args[0]
    assert "Use /setstyle <style description>" in args[0]

@pytest.mark.asyncio
async def test_set_style_command_with_style(mock_context, mock_style_memory):
    user_id = 123
    style_prompt = "witty and informal"
    mock_context.args = [style_prompt]

    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    update.message.reply_text = AsyncMock()
    update.effective_user.id = user_id

    await set_style_command(update, mock_context)

    update.message.reply_text.assert_called_once_with(f"Your writing style has been set to: '{style_prompt}'.")
    stored_style = await mock_style_memory.get_style(user_id)
    assert stored_style == style_prompt

@pytest.mark.asyncio
async def test_set_style_command_no_style_provided_no_existing_style(mock_context, mock_style_memory):
    user_id = 123
    mock_context.args = [] # No style provided

    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    update.message.reply_text = AsyncMock()
    update.effective_user.id = user_id

    await set_style_command(update, mock_context)

    update.message.reply_text.assert_called_once()
    args, kwargs = update.message.reply_text.call_args
    assert "Please provide a style description." in args[0]
    assert "Example: /setstyle" in args[0]
    stored_style = await mock_style_memory.get_style(user_id)
    assert stored_style is None

@pytest.mark.asyncio
async def test_set_style_command_no_style_provided_with_existing_style(mock_context, mock_style_memory):
    user_id = 123
    existing_style = "formal and concise"
    await mock_style_memory.set_style(user_id, existing_style)
    mock_context.args = [] # No style provided

    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    update.message.reply_text = AsyncMock()
    update.effective_user.id = user_id

    await set_style_command(update, mock_context)

    update.message.reply_text.assert_called_once_with(
        f"Your current style is: '{existing_style}'.\n\nTo change it, use /setstyle <new style description>."
    )
    stored_style = await mock_style_memory.get_style(user_id)
    assert stored_style == existing_style # Should not have changed

@pytest.mark.asyncio
async def test_set_style_command_error_handling(mock_context, mock_style_memory):
    user_id = 123
    style_prompt = "error inducing style"
    mock_context.args = [style_prompt]

    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    update.message.reply_text = AsyncMock()
    update.effective_user.id = user_id

    # Simulate an error in the style memory
    mock_style_memory.set_style = AsyncMock(side_effect=Exception("DB write error"))

    await set_style_command(update, mock_context)

    update.message.reply_text.assert_called_once_with("An error occurred while saving your style. Please try again later.")
    mock_style_memory.set_style.assert_called_once_with(user_id, style_prompt)
