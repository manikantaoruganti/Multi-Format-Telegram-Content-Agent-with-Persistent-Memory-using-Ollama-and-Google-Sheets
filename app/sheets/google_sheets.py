import gspread
import base64
import json
import logging
from app.config.settings import Settings
from app.utils.retry import retry_async

logger = logging.getLogger(__name__)

class GoogleSheetsError(Exception):
    """Custom exception for Google Sheets operation failures."""
    pass

class GoogleSheetsClient:
    """
    Client for interacting with Google Sheets.
    Handles authentication, worksheet initialization, and data appending.
    """
    REQUIRED_HEADERS = [
        "SourceIdentifier",
        "SubmissionTimestamp",
        "ContentType",
        "LLMTitle",
        "Rationale",
        "Category",
        "X_Variant",
        "LinkedIn_Variant"
    ]

    def __init__(self, settings: Settings):
        self.settings = settings
        self._gc = self._authenticate()
        self._spreadsheet = self._gc.open_by_id(settings.GOOGLE_SPREADSHEET_ID)
        self._worksheet = None # Will be initialized on first use

    def _authenticate(self) -> gspread.Client:
        """Authenticates with Google using Base64 encoded service account credentials."""
        try:
            credentials_json_b64 = self.settings.GOOGLE_SHEETS_CREDENTIALS_B64
            credentials_json_bytes = base64.b64decode(credentials_json_b64)
            credentials_dict = json.loads(credentials_json_bytes)
            gc = gspread.service_account_from_dict(credentials_dict)
            logger.info("Google Sheets authentication successful.")
            return gc
        except Exception as e:
            logger.critical(f"Failed to authenticate with Google Sheets: {e}", exc_info=True)
            raise GoogleSheetsError(f"Google Sheets authentication failed: {e}") from e

    @retry_async(max_retries_key="MAX_RETRIES", delay_key="RETRY_DELAY_SECONDS", logger=logger,
                 retry_exceptions=(gspread.exceptions.APIError, gspread.exceptions.GSpreadException))
    async def _get_worksheet(self) -> gspread.Worksheet:
        """Retrieves the worksheet and initializes headers if necessary."""
        if self._worksheet:
            return self._worksheet

        try:
            self._worksheet = self._spreadsheet.worksheet(self.settings.GOOGLE_WORKSHEET_NAME)
            logger.debug(f"Connected to worksheet: {self.settings.GOOGLE_WORKSHEET_NAME}")
        except gspread.exceptions.WorksheetNotFound:
            logger.info(f"Worksheet '{self.settings.GOOGLE_WORKSHEET_NAME}' not found, creating it.")
            self._worksheet = self._spreadsheet.add_worksheet(self.settings.GOOGLE_WORKSHEET_NAME, rows=1, cols=len(self.REQUIRED_HEADERS))
            logger.info(f"Worksheet '{self.settings.GOOGLE_WORKSHEET_NAME}' created.")
        except Exception as e:
            logger.error(f"Error accessing or creating worksheet: {e}", exc_info=True)
            raise GoogleSheetsError(f"Failed to access or create worksheet: {e}") from e

        # Check and initialize headers
        current_headers = await asyncio.to_thread(self._worksheet.row_values, 1)
        if not current_headers or current_headers != self.REQUIRED_HEADERS:
            logger.info("Worksheet headers are missing or incorrect, initializing them.")
            await asyncio.to_thread(self._worksheet.update, [self.REQUIRED_HEADERS], "A1")
            logger.info("Worksheet headers initialized.")
        else:
            logger.debug("Worksheet headers are correct.")

        return self._worksheet

    @retry_async(max_retries_key="MAX_RETRIES", delay_key="RETRY_DELAY_SECONDS", logger=logger,
                 retry_exceptions=(gspread.exceptions.APIError, gspread.exceptions.GSpreadException))
    async def append_row(self, row_data: list[str]) -> None:
        """
        Appends a row of data to the configured Google Sheet worksheet.
        Initializes headers if they are missing.
        """
        worksheet = await self._get_worksheet()
        try:
            # gspread operations are synchronous, so run in a thread pool
            await asyncio.to_thread(worksheet.append_row, row_data)
            logger.info(f"Row appended to Google Sheet: {row_data[0]}...")
        except Exception as e:
            logger.error(f"Failed to append row to Google Sheet: {e}", exc_info=True)
            raise GoogleSheetsError(f"Failed to append row: {e}") from e
