import asyncio
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from aiohttp import web

from app.bot.handlers import start_command, set_style_command, message_handler, error_handler
from app.config.settings import Settings
from app.services.ingestion_service import IngestionService
from app.database.style_memory import StyleMemory
from app.database.database import init_db

logger = logging.getLogger(__name__)

class TelegramService:
    def __init__(self, settings: Settings, ingestion_service: IngestionService, style_memory: StyleMemory):
        self.settings = settings
        self.ingestion_service = ingestion_service
        self.style_memory = style_memory
        self.application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

        # Store services in bot_data for handlers to access
        self.application.bot_data['ingestion_service'] = self.ingestion_service
        self.application.bot_data['style_memory'] = self.style_memory

        self._register_handlers()

    def _register_handlers(self) -> None:
        """Registers all command and message handlers."""
        self.application.add_handler(CommandHandler("start", start_command))
        self.application.add_handler(CommandHandler("setstyle", set_style_command))
        self.application.add_handler(MessageHandler(filters.TEXT | filters.Document.PDF, message_handler))
        self.application.add_error_handler(error_handler)
        logger.info("Telegram handlers registered.")

    async def _run_health_check_server(self) -> None:
        """Runs a lightweight HTTP server for health checks."""
        async def health_check(request):
            return web.json_response({"status": "healthy"})

        app = web.Application()
        app.router.add_get("/health", health_check)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.settings.HEALTH_HOST, self.settings.HEALTH_PORT)
        logger.info(f"Health check server starting on http://{self.settings.HEALTH_HOST}:{self.settings.HEALTH_PORT}/health")
        await site.start()
        # Keep the server running indefinitely
        await asyncio.Event().wait()

    async def run(self) -> None:
        """Starts the Telegram bot with long polling and the health check server."""
        logger.info("Initializing database...")
        await init_db(self.settings.STYLE_DB_PATH, self.settings.GENERATION_DB_PATH)
        logger.info("Database initialized.")

        logger.info("Starting Telegram bot (long polling)...")
        # Run long polling and health check server concurrently
        await asyncio.gather(
            self.application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True),
            self._run_health_check_server()
        )
        logger.info("Telegram bot and health check server stopped.")
