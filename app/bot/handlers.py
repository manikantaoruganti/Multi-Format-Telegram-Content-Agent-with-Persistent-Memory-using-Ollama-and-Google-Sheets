import logging
from telegram import Update
from telegram.ext import ContextTypes

from app.services.ingestion_service import IngestionService
from app.database.style_memory import StyleMemory
from app.utils.validation import is_valid_url

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message and explains bot usage."""
    if update.message:
        welcome_message = (
            "Welcome to the Content Team Agent!\n\n"
            "Send me:\n"
            "• plain text\n"
            "• an article URL (e.g., https://example.com/article)\n"
            "• a PDF document\n\n"
            "I will analyze the content and generate:\n"
            "• title\n"
            "• editorial rationale\n"
            "• category\n"
            "• X post (Twitter)\n"
            "• LinkedIn post\n\n"
            "Use /setstyle <style description> to save your preferred writing style. "
            "Example: /setstyle Write in a witty, informal tone and always include a useful data point."
        )
        await update.message.reply_text(welcome_message)
        logger.info(f"User {update.effective_user.id} received start message.")

async def set_style_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sets or updates the user's preferred writing style."""
    if not update.message or not update.effective_user:
        logger.warning("Received set_style command without message or effective user.")
        return

    user_id = update.effective_user.id
    style_prompt = " ".join(context.args).strip()

    style_memory: StyleMemory = context.bot_data['style_memory']

    if not style_prompt:
        current_style = await style_memory.get_style(user_id)
        if current_style:
            await update.message.reply_text(
                f"Your current style is: '{current_style}'.\n\n"
                "To change it, use /setstyle <new style description>."
            )
        else:
            await update.message.reply_text(
                "Please provide a style description. "
                "Example: /setstyle Write in a witty, informal tone and always include a useful data point."
            )
        logger.info(f"User {user_id} requested /setstyle usage or current style.")
        return

    try:
        await style_memory.set_style(user_id, style_prompt)
        await update.message.reply_text(f"Your writing style has been set to: '{style_prompt}'.")
        logger.info(f"User {user_id} set style to: '{style_prompt[:50]}...'")
    except Exception as e:
        logger.error(f"Failed to set style for user {user_id}: {e}", exc_info=True)
        await update.message.reply_text("An error occurred while saving your style. Please try again later.")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming messages, routing them based on content type."""
    if not update.message or not update.effective_user:
        logger.warning("Received message without message or effective user.")
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    ingestion_service: IngestionService = context.bot_data['ingestion_service']

    try:
        if update.message.document and update.message.document.mime_type == 'application/pdf':
            await update.message.reply_text("Received PDF. Processing...")
            await ingestion_service.process_pdf(user_id, chat_id, update.message.document)
        elif update.message.text:
            text_content = update.message.text.strip()
            if is_valid_url(text_content):
                await update.message.reply_text("Received URL. Fetching content...")
                await ingestion_service.process_url(user_id, chat_id, text_content)
            elif text_content.startswith('/'): # Ignore other commands
                logger.info(f"User {user_id} sent an unknown command: {text_content}")
                return
            elif text_content:
                await update.message.reply_text("Received text. Analyzing...")
                await ingestion_service.process_plain_text(user_id, chat_id, text_content)
            else:
                await update.message.reply_text("Please send some text, a URL, or a PDF document.")
                logger.info(f"User {user_id} sent empty text message.")
        else:
            await update.message.reply_text("Unsupported message type. Please send text, a URL, or a PDF document.")
            logger.info(f"User {user_id} sent unsupported message type: {update.message.effective_attachment}")

    except Exception as e:
        logger.error(f"Error processing message for user {user_id}: {e}", exc_info=True)
        await update.message.reply_text(
            "An unexpected error occurred while processing your request. "
            "Please try again later or contact support."
        )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to the user."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "An internal error occurred. We've been notified and are looking into it."
        )
