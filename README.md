
# Multi-Format Telegram Content Agent

## Overview

The Multi-Format Telegram Content Agent is a robust, production-minded application designed to streamline content generation for social media platforms. It acts as an intelligent assistant, accepting various content inputs (plain text, web URLs, PDF documents) via Telegram. The agent processes this content, leverages a Large Language Model (LLM) powered by Ollama to generate structured, platform-specific content (X posts, LinkedIn posts), applies persistent user-specific writing styles, and then idempotently writes the results to Google Sheets.

This project emphasizes clean architecture, resilience, and testability, making it suitable for deployment in dynamic environments.

## Features

*   **Telegram Bot Interface**: Interact via `/start`, `/setstyle <style>`, and by sending text, URLs, or PDFs.
*   **Multi-Format Content Ingestion**:
    *   **Plain Text**: Direct text input.
    *   **Web URLs**: Extracts main article content using `trafilatura`.
    *   **PDF Documents**: Extracts structured markdown from PDFs using `pdftotext` (via `markitdown` dependency).
*   **Ollama LLM Integration**: Utilizes a local or remote Ollama instance for content generation.
*   **Structured JSON LLM Output**: Ensures consistent and validated output from the LLM.
*   **LLM Output Validation & Correction**: Implements retry logic with correction prompts for malformed JSON, X post character limits, and distinct X/LinkedIn content.
*   **Persistent User-Specific Style Memory**: Stores and applies user-defined writing styles using SQLite.
*   **Google Sheets Integration**: Writes generated content to a specified Google Sheet with exact, predefined headers.
*   **Idempotent Writes**: Prevents duplicate entries in Google Sheets based on a unique combination of source, user, and style.
*   **Robust Long Polling**: Handles Telegram updates with resilience against network errors and temporary failures.
*   **Error Handling & Retries**: Comprehensive error management with exponential backoff for external API calls (Ollama, Google Sheets, HTTP requests).
*   **Dockerized Application**: Packaged with Docker and `docker-compose` for easy setup and deployment.
*   **Health Check**: A lightweight HTTP server for Docker health monitoring.
*   **Comprehensive Testing**: Unit and integration tests covering all critical components and scenarios.
*   **Security**: Environment variable-based configuration, Base64-encoded Google credentials, and `.gitignore` for secrets.

## Architecture

The system is designed with clear separation of concerns, following a layered architecture to ensure modularity and maintainability.

```mermaid
flowchart TD
    A[Telegram User] --> B[Telegram Bot API]
    B --> C[Long Polling]
    C --> D[Ingestion Service]
    D --> E{Content Type Router}
    E -->|Plain Text| F[Text Extractor]
    E -->|URL| G[URL Extractor (Trafilatura)]
    E -->|PDF| H[PDF Extractor (MarkItDown/pdftotext)]
    F --> I[LLM Orchestrator]
    G --> I
    H --> I
    J[SQLite Style Memory] --> I
    I --> K[Ollama / LLM]
    K --> L[JSON Validator]
    L --> M[Idempotency Layer]
    M --> N[Google Sheets]
    I --> O[Telegram Response]
```

**Flow Description:**

1.  **Telegram User** interacts with the **Telegram Bot API**.
2.  The **Telegram Bot API** sends updates to the application via **Long Polling**.
3.  The **Ingestion Service** receives updates and routes them through the **Content Type Router**.
4.  Based on content type, the router directs to:
    *   **Plain Text**: Processed by the **Text Extractor**.
    *   **URL**: Fetched and extracted by the **URL Extractor** (using `trafilatura`).
    *   **PDF**: Downloaded, converted to Markdown, and extracted by the **PDF Extractor** (using `pdftotext` via `markitdown`).
5.  Extracted content, along with the user's **Persistent Style Memory** (SQLite), is sent to the **LLM Orchestrator**.
6.  The **LLM Orchestrator** interacts with **Ollama / LLM** to generate structured content.
7.  The raw LLM output undergoes **Structured JSON Validation** and correction.
8.  The validated output proceeds to the **Idempotency Layer**, which checks against previous generations stored in SQLite.
9.  If unique, the content is written to **Google Sheets**.
10. Finally, a **Telegram Response** is sent back to the user, indicating success or failure.

## Technology Stack

*   **Python**: Core programming language.
*   **`python-telegram-bot`**: For Telegram Bot API interaction.
*   **Ollama**: Local/remote LLM provider.
*   **SQLite**: For persistent user style memory and idempotency records.
*   **`gspread`**: For Google Sheets integration.
*   **`trafilatura`**: For robust web article extraction.
*   **`markitdown` (via `pdftotext`)**: For PDF to Markdown conversion and text extraction.
*   **`aiohttp` / `aiofiles`**: For asynchronous HTTP requests and file operations.
*   **`tenacity`**: For robust retry logic with exponential backoff.
*   **`pydantic` / `pydantic-settings`**: For data validation and settings management.
*   **Docker**: Containerization.
*   **Docker Compose**: Orchestration of multi-container applications.
*   **`pytest`**: For comprehensive testing.
*   **`uvicorn`**: For running the health check server.

## Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── handlers.py         # Telegram command and message handlers
│   │   └── telegram_service.py   # Initializes and runs the Telegram bot and health server
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py         # Loads and validates environment variables
│   ├── database/
│   │   ├── __init__.py
│   │   ├── database.py         # SQLite database initialization
│   │   ├── style_memory.py     # Manages user-specific styles in SQLite
│   │   └── idempotency_store.py # Manages processed generation keys in SQLite
│   ├── extractors/
│   │   ├── __init__.py
│   │   ├── text_extractor.py   # Extracts and normalizes plain text
│   │   ├── url_extractor.py    # Extracts content from URLs using Trafilatura
│   │   └── pdf_extractor.py    # Extracts content from PDFs using MarkItDown/pdftotext
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── ollama_client.py    # Client for Ollama API interaction
│   │   ├── prompts.py          # Defines LLM system, user, and correction prompts
│   │   └── validator.py        # Validates and corrects LLM JSON output
│   ├── sheets/
│   │   ├── __init__.py
│   │   └── google_sheets.py    # Client for Google Sheets API interaction
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ingestion_service.py # Orchestrates the full content processing pipeline
│   │   ├── content_service.py   # Routes and manages content extraction
│   │   └── idempotency_service.py # Manages generation key creation and checks
│   ├── models/
│   │   ├── __init__.py
│   │   └── content.py          # Pydantic models for LLM output and internal content representation
│   └── utils/
│       ├── __init__.py
│       ├── hashing.py          # SHA256 hashing utilities
│       ├── retry.py            # Asynchronous retry decorator with exponential backoff
│       └── validation.py       # General validation utilities (URL, X post length)
│
├── tests/
│   ├── unit/                   # Unit tests for individual components
│   │   ├── test_extractors.py
│   │   ├── test_style_memory.py
│   │   ├── test_idempotency.py
│   │   ├── test_prompt.py
│   │   ├── test_llm_validator.py
│   │   └── test_router.py
│   └── integration/            # Integration tests for service interactions and full pipeline
│       ├── test_bot_handlers.py
│       └── test_content_pipeline.py
│
├── Dockerfile                  # Docker build instructions for the application
├── docker-compose.yml          # Defines multi-service Docker application (app + ollama)
├── .env.example                # Example environment variables
├── .gitignore                  # Specifies files/directories to ignore in Git
├── requirements.txt            # Python dependencies
└── README.md                   # Project documentation
```

## Prerequisites

Before running the application, ensure you have:

*   **Docker** and **Docker Compose** installed on your system.
*   A **Telegram Bot Token** from BotFather.
*   A **Google Cloud Project** with the Google Sheets API enabled.
*   A **Google Service Account** with access to your Google Sheet.
*   The **JSON credentials** for the service account, Base64 encoded.
*   A **Google Spreadsheet ID** and **Worksheet Name**.

## Telegram Bot Setup

1.  **Create a new bot** by talking to [@BotFather](https://t.me/BotFather) on Telegram.
2.  BotFather will give you a **Telegram Bot Token**. Save this token.

## Google Sheets Setup

1.  **Create a new Google Spreadsheet** or use an existing one. Note its **Spreadsheet ID** from the URL (e.g., `https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID/edit`).
2.  **Enable the Google Sheets API**:
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Select or create a project.
    *   Navigate to "APIs & Services" > "Library".
    *   Search for "Google Sheets API" and enable it.
3.  **Create a Service Account**:
    *   In the Google Cloud Console, go to "APIs & Services" > "Credentials".
    *   Click "Create Credentials" > "Service Account".
    *   Give it a name and description.
    *   Grant it the "Editor" role (or a more specific role like "Google Sheets Editor") on your project.
    *   Click "Done".
4.  **Generate a JSON Key**:
    *   On the "Credentials" page, find your newly created service account.
    *   Click on its email address.
    *   Go to the "Keys" tab.
    *   Click "Add Key" > "Create new key" > "JSON".
    *   A JSON file will be downloaded. **Keep this file secure.**
5.  **Share your Spreadsheet with the Service Account**:
    *   Open your Google Spreadsheet.
    *   Click the "Share" button.
    *   Add the **email address of your service account** (found in the downloaded JSON file, under `client_email`) as an editor.
6.  **Base64 Encode the JSON Credentials**:
    *   Open the downloaded JSON file.
    *   Copy its entire content.
    *   Use a tool or command line to Base64 encode it. For example, on Linux/macOS:
        ```bash
        cat your-service-account-key.json | base64
        ```
        On Windows (PowerShell):
        ```powershell
        [System.Convert]::ToBase64String([System.IO.File]::ReadAllBytes("your-service-account-key.json"))
        ```
    *   Save the resulting Base64 string. This will be your `GOOGLE_SHEETS_CREDENTIALS_B64`.

## Ollama Setup

The `docker-compose.yml` includes an `ollama` service that will automatically pull the specified model (`llama3.1` by default) on startup if it's not already present. This simplifies local development.

## Environment Variables

Create a `.env` file in the root directory of the project (next to `docker-compose.yml`) based on `.env.example`. Replace the placeholder values with your actual credentials and desired settings.

```ini
TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
GOOGLE_SHEETS_CREDENTIALS_B64=YOUR_BASE64_GOOGLE_SERVICE_ACCOUNT_JSON
GOOGLE_SPREADSHEET_ID=YOUR_SPREADSHEET_ID
GOOGLE_WORKSHEET_NAME=Content

LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.1

STYLE_DB_PATH=/data/styles.db
GENERATION_DB_PATH=/data/generations.db

HEALTH_HOST=0.0.0.0
HEALTH_PORT=8080

LLM_TIMEOUT_SECONDS=120
MAX_RETRIES=3
RETRY_DELAY_SECONDS=2

MAX_URL_CONTENT_SIZE_MB=5
MAX_PDF_FILE_SIZE_MB=10
```

*   `TELEGRAM_BOT_TOKEN`: Your Telegram bot token.
*   `GOOGLE_SHEETS_CREDENTIALS_B64`: The Base64 encoded JSON string of your Google Service Account credentials.
*   `GOOGLE_SPREADSHEET_ID`: The ID of your Google Spreadsheet.
*   `GOOGLE_WORKSHEET_NAME`: The name of the worksheet to use (e.g., `Content`).
*   `LLM_PROVIDER`: Currently only `ollama` is supported.
*   `OLLAMA_BASE_URL`: The URL where your Ollama instance is accessible. If running via `docker-compose`, `http://ollama:11434` is correct.
*   `OLLAMA_MODEL`: The specific Ollama model to use (e.g., `llama3.1`).
*   `STYLE_DB_PATH`: Path inside the container for the SQLite style database. Mapped to a Docker volume.
*   `GENERATION_DB_PATH`: Path inside the container for the SQLite generation idempotency database. Mapped to a Docker volume.
*   `HEALTH_HOST`, `HEALTH_PORT`: Configuration for the health check server.
*   `LLM_TIMEOUT_SECONDS`: Timeout for LLM API calls.
*   `MAX_RETRIES`, `RETRY_DELAY_SECONDS`: Global retry settings for transient errors.
*   `MAX_URL_CONTENT_SIZE_MB`, `MAX_PDF_FILE_SIZE_MB`: Limits for content extraction to prevent resource exhaustion.

## Local Development

While Docker is recommended for full setup, you can run parts locally for development:

1.  **Install Python dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
2.  **Run the application**:
    ```bash
    python app/main.py
    ```
    Note: This requires Ollama to be running and accessible at `OLLAMA_BASE_URL`, and your `.env` file to be correctly configured. SQLite databases will be created in the current directory or specified path.

## Docker Setup

The recommended way to run this application is using Docker Compose.

1.  **Ensure Docker and Docker Compose are installed.**
2.  **Create your `.env` file** as described in the Environment Variables section.
3.  **Build and run the services**:
    ```bash
    docker compose up --build -d
    ```
    This command will:
    *   Build the `app` service Docker image.
    *   Pull the `ollama/ollama` image.
    *   Start both `ollama` and `app` services in detached mode.
    *   The `ollama` service will attempt to pull the `OLLAMA_MODEL` (default `llama3.1`) on startup.
    *   The `app` service will wait for `ollama` to be healthy before starting.
    *   Create Docker volumes for persistent SQLite data and Ollama models.

4.  **Check service status**:
    ```bash
    docker compose ps
    ```
    You should see both `ollama` and `telegram-content-agent` services running.

## Health Check

The application exposes a simple HTTP endpoint for health checks.

To check the health of the `app` service:

```bash
curl http://localhost:8080/health
```

Expected output:
```json
{"status": "healthy"}
```

The `docker-compose.yml` is configured with a healthcheck that uses this endpoint to monitor the application's status.

## Testing

The project includes a comprehensive suite of `pytest` tests.

1.  **Ensure Python dependencies are installed** (including `pytest`, `pytest-asyncio`).
2.  **Run tests**:
    ```bash
    pytest -q
    ```
    This will execute all unit and integration tests. Unit tests are designed to run without external credentials by mocking API calls.

## Usage

Once the Docker containers are running, interact with your Telegram bot:

*   **/start**: Sends a welcome message explaining the bot's capabilities.
*   **/setstyle <style description>**: Sets your preferred writing style.
    *   Example: `/setstyle Write in a witty, informal tone and always include a useful data point.`
    *   If no style is provided (`/setstyle`), it will show your current style or usage instructions.
*   **Send plain text**: The bot will analyze it and generate content.
*   **Send a URL**: The bot will fetch the article content, analyze it, and generate content.
*   **Send a PDF document**: The bot will download, extract text, analyze it, and generate content.

## Example Workflow

1.  **Start the bot**: `docker compose up --build -d`
2.  **In Telegram, send `/start`** to your bot. You'll receive the welcome message.
3.  **Set your style**: Send `/setstyle Be very concise and use emojis where appropriate.`
4.  **Send content**:
    *   **Text**: `Tell me about the latest advancements in quantum computing.`
    *   **URL**: `https://www.theverge.com/2024/7/18/24200000/apple-ai-ios-18-siri-openai-chatgpt-privacy-on-device`
    *   **PDF**: Upload a PDF document.
5.  The bot will respond with "Received X. Analyzing..." and then "Content successfully processed and saved to Google Sheets!" (or an error message if something went wrong).
6.  Check your configured Google Sheet for the new entries.

## LLM Prompt Strategy

The LLM interaction uses a structured prompting approach:

*   **System Prompt**: Defines the LLM's persona as an "expert content strategist and social media specialist" and strictly outlines output format (JSON only) and content constraints (X post length, distinct variants, etc.).
*   **User Prompt**: Provides the specific content to analyze, its type, and crucially, the user's `Preferred Style`.
*   **Correction Prompt**: If the initial LLM output is invalid (malformed JSON, schema violation, X post too long, identical X/LinkedIn), a specific correction prompt is sent to the LLM, referencing the previous invalid response and reiterating the strict output requirements. This ensures robust output.
*   **Specific Prompts for X/LinkedIn Correction**: Dedicated prompts are used to ask the LLM to shorten an X post or make a LinkedIn post distinct, rather than attempting to fix these programmatically via truncation or simple appending.

## Persistent Style Memory

User-specific writing styles are stored in an SQLite database (`user_styles` table) with the following schema:

*   `user_id` (INTEGER PRIMARY KEY)
*   `style_prompt` (TEXT NOT NULL)
*   `updated_at` (TEXT NOT NULL)

This database is mounted as a Docker volume (`/data:/data`) to ensure styles persist across container restarts. The `StyleMemory` service provides `set_style` and `get_style` methods.

## Idempotency Strategy

Idempotency is critical to prevent duplicate entries in Google Sheets, especially when dealing with retries or accidental re-submissions. The strategy is based on a unique "generation key" that combines:

`generation_key = SHA256(user_id + source_identifier + style_hash)`

*   `user_id`: The Telegram user who initiated the request.
*   `source_identifier`: A unique hash of the content (SHA256 for text/PDF, original URL for URLs).
*   `style_hash`: A SHA256 hash of the user's `style_prompt` at the time of processing.

This `generation_key` is stored in a separate SQLite table (`processed_generations`) *before* writing to Google Sheets.

**Behavior:**

*   **Same source + same user + same style**: The `generation_key` will be identical. The `IdempotencyService` will detect this and prevent a new row from being appended to Google Sheets, sending a "content already processed" message to the user.
*   **Same source + same user + changed style**: The `style_hash` will change, resulting in a new `generation_key`. This correctly allows a new row to be created in Google Sheets, reflecting the new style applied to the same source content.

The `processed_generations` table schema:

*   `generation_key` (TEXT PRIMARY KEY)
*   `user_id` (INTEGER NOT NULL)
*   `source_identifier` (TEXT NOT NULL)
*   `style_hash` (TEXT NOT NULL)
*   `created_at` (TEXT NOT NULL)

This table is also mounted as a Docker volume for persistence.

## Error Handling

The application implements robust error handling at various layers:

*   **Specific Exception Classes**: Custom exceptions (e.g., `URLExtractionError`, `PDFExtractionError`, `LLMClientError`, `LLMValidationException`, `GoogleSheetsError`) are used to categorize and handle errors precisely.
*   **Graceful Degradation**: The bot is designed not to crash. Instead, it logs detailed diagnostic information (without secrets) and sends user-friendly error messages back to the Telegram user, avoiding exposing stack traces.
*   **`try...except` Blocks**: Used extensively around external API calls, file operations, and data processing steps.
*   **Resource Safety**: Limits are imposed on URL content size and PDF file size to prevent resource exhaustion. Temporary files are always cleaned up using `finally` blocks.

## Retry Strategy

A reusable asynchronous retry decorator (`@retry_async`) is implemented using `tenacity` with exponential backoff. This decorator is applied to transient network/API operations:

*   **Ollama API calls**: Retries on connection errors, timeouts, and specific Ollama API errors.
*   **Google Sheets API calls**: Retries on `gspread` API errors and general exceptions.
*   **URL fetching**: Retries on `aiohttp` client errors and timeouts.

Retries are configured via environment variables (`MAX_RETRIES`, `RETRY_DELAY_SECONDS`) and have a maximum attempt limit to prevent infinite loops. Permanent errors (e.g., invalid configuration, unsupported content types) are not retried.

## Security

*   **Environment Variables**: All sensitive information (Telegram token, Google credentials, API keys) is loaded from environment variables at runtime, never hardcoded.
*   **Base64 Encoded Credentials**: Google Service Account JSON credentials are Base64 encoded in the `.env` file and decoded at runtime, preventing the raw JSON file from being committed or directly exposed.
*   **`.gitignore`**: Configured to ignore `.env`, SQLite database files, Python bytecode, and temporary files, ensuring secrets and build artifacts are not committed to version control.
*   **Non-Root User**: The Dockerfile runs the application as a non-root `appuser` for enhanced security.
*   **No Logging of Secrets**: Sensitive data is explicitly excluded from logs.

## Long Polling vs Webhook

**Long polling was selected as the primary mechanism** for Telegram updates in this project for the following reasons:

1.  **Resilience in Free-Tier/Ephemeral Environments**: The task specifically mentions free-tier environments where services can sleep or be restarted frequently. Long polling is more resilient in such scenarios because the application actively maintains the update connection. If the application restarts, it simply re-establishes the long polling connection and continues receiving updates.
2.  **No Publicly Accessible Endpoint Required**: Long polling does not require the application to be publicly accessible on the internet, which simplifies deployment, especially in environments without fixed IP addresses or easy port forwarding. This is a significant advantage for local development or deployments behind restrictive firewalls.
3.  **Simpler Infrastructure**: It avoids the complexities of setting up and managing webhooks, such as SSL certificates, domain names, and ensuring the server is always reachable by Telegram's API.

**Webhook Trade-offs (Why not chosen):**

*   **Requires Public Endpoint**: A webhook setup necessitates a publicly accessible HTTPS endpoint for Telegram to send updates to. This often involves configuring a domain, SSL certificates, and exposing a port, which can be more complex for simple deployments or free-tier services.
*   **Downtime for Updates**: If the webhook endpoint is temporarily down or unreachable, Telegram might retry sending updates, but there's a risk of missed updates if the downtime is prolonged or if Telegram's retry mechanism gives up.
*   **Scalability Considerations**: While webhooks can be more scalable for very high-volume bots by offloading the polling responsibility to Telegram, for typical agent-based use cases, long polling is often sufficient and simpler to manage.

This implementation does **NOT** claim webhook support.

## Scalability

For hundreds or thousands of users, several aspects of this architecture would need to be considered or modified:

*   **Database**: SQLite is excellent for single-instance, low-to-medium concurrency. For high concurrency or distributed deployments, migrating to a robust relational database like PostgreSQL (with a proper ORM like SQLAlchemy) or a NoSQL solution would be necessary.
*   **LLM Throughput**: A single Ollama instance might become a bottleneck.
    *   **Scaling Ollama**: Deploying multiple Ollama instances behind a load balancer.
    *   **Cloud LLMs**: Integrating with scalable cloud LLM providers (e.g., Groq, OpenAI, Gemini) that can handle higher request volumes. The `LLMClient` abstraction allows for easy integration of different providers.
*   **Telegram Bot**: `python-telegram-bot` with long polling is suitable for many users, but for extremely high volumes, a distributed setup with multiple bot instances (e.g., using a message queue like RabbitMQ or Kafka to distribute updates) might be required.
*   **Google Sheets Rate Limits**: Google Sheets API has rate limits. For very high write volumes, a queueing mechanism (e.g., a background worker processing writes from a Redis queue) would be essential to buffer requests and prevent hitting limits. Batching writes could also improve efficiency.
*   **Asynchronous Processing**: The current use of `asyncio` and `aiohttp` provides good concurrency within a single application instance, but for true horizontal scaling, a task queue (e.g., Celery with Redis/RabbitMQ) could offload heavy processing (like PDF extraction or LLM calls) to worker processes.
*   **File Storage**: Temporary file storage for PDFs (`/tmp`) is local to the container. In a multi-instance deployment, a shared object storage solution (e.g., S3, Google Cloud Storage) would be needed for temporary files.

## Troubleshooting

*   **`docker compose up --build -d` fails**:
    *   Check Docker is running.
    *   Verify `docker-compose.yml` syntax (`docker compose config`).
    *   Check Docker logs for specific errors: `docker compose logs app`.
*   **Bot not responding**:
    *   Ensure `TELEGRAM_BOT_TOKEN` in `.env` is correct.
    *   Check `app` service logs: `docker compose logs app`. Look for "Telegram bot (long polling) started" or any errors.
    *   Verify network connectivity from the `app` container to `ollama` (if running locally).
*   **LLM errors**:
    *   Ensure `ollama` service is running and healthy: `docker compose ps`.
    *   Check `ollama` logs: `docker compose logs ollama`.
    *   Verify `OLLAMA_BASE_URL` and `OLLAMA_MODEL` in `.env` are correct.
    *   Ensure the specified Ollama model has been pulled successfully.
*   **Google Sheets errors**:
    *   Verify `GOOGLE_SHEETS_CREDENTIALS_B64`, `GOOGLE_SPREADSHEET_ID`, `GOOGLE_WORKSHEET_NAME` in `.env` are correct.
    *   Ensure the service account email has "Editor" access to your Google Sheet.
    *   Check `app` service logs for `GoogleSheetsError`.
*   **PDF processing errors**:
    *   Check `app` service logs for `PDFExtractionError`. This might indicate issues with `pdftotext` (installed via `poppler-utils` in Dockerfile) or the PDF itself.
*   **Health check fails**:
    *   Ensure the `app` service is running.
    *   Check `HEALTH_HOST` and `HEALTH_PORT` in `.env` match the `docker-compose.yml` configuration.
    *   Check `app` service logs for messages related to the health check server startup.

---

## Summary

This project delivers a fully functional, production-minded Telegram content agent with robust features for multi-format content ingestion, LLM-powered generation, persistent style memory, and idempotent Google Sheets integration. It adheres to all specified requirements, emphasizing clean architecture, resilience, and testability.

### Complete File Tree

```
.
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── handlers.py
│   │   └── telegram_service.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── idempotency_store.py
│   │   └── style_memory.py
│   ├── extractors/
│   │   ├── __init__.py
│   │   ├── text_extractor.py
│   │   ├── url_extractor.py
│   │   └── pdf_extractor.py
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── ollama_client.py
│   │   ├── prompts.py
│   │   └── validator.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── content.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── content_service.py
│   │   ├── idempotency_service.py
│   │   └── ingestion_service.py
│   ├── sheets/
│   │   ├── __init__.py
│   │   └── google_sheets.py
│   └── utils/
│       ├── __init__.py
│       ├── hashing.py
│       ├── retry.py
│       └── validation.py
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
└── tests/
    ├── __init__.py
    ├── integration/
    │   ├── __init__.py
    │   ├── test_bot_handlers.py
    │   └── test_content_pipeline.py
    └── unit/
        ├── __init__.py
        ├── test_extractors.py
        ├── test_idempotency.py
        ├── test_llm_validator.py
        ├── test_prompt.py
        ├── test_router.py
        └── test_style_memory.py
```

### Main Architecture

The architecture follows a layered approach:

1.  **Telegram Ingestion Layer**: Handles updates via long polling, routes messages.
2.  **Content Extraction Layer**: Extracts content from text, URLs (Trafilatura), and PDFs (MarkItDown/pdftotext).
3.  **LLM Orchestration Layer**: Manages user styles (SQLite), interacts with Ollama, and validates/corrects LLM output.
4.  **Idempotency Layer**: Prevents duplicate processing based on source, user, and style (SQLite).
5.  **Google Sheets Integration Layer**: Writes validated content to Google Sheets.

### Commands to Install/Run

1.  **Create `.env`**: Copy `.env.example` to `.env` and fill in your credentials.
2.  **Build and Run with Docker Compose**:
    ```bash
    docker compose up --build -d
    ```

### Commands to Test

1.  **Install Python dependencies (if running tests outside Docker)**:
    ```bash
    pip install -r requirements.txt
    ```
2.  **Run Pytest**:
    ```bash
    pytest -q
    ```

### Docker Commands

*   **Build and run**: `docker compose up --build -d`
*   **Stop services**: `docker compose down`
*   **View running services**: `docker compose ps`
*   **View logs**: `docker compose logs -f app` (for the main application)
*   **Check health**: `curl http://localhost:8080/health`

### Environment Variables

All environment variables are listed in `.env.example` and are critical for the application's operation. They include:

*   `TELEGRAM_BOT_TOKEN`
*   `GOOGLE_SHEETS_CREDENTIALS_B64`
*   `GOOGLE_SPREADSHEET_ID`
*   `GOOGLE_WORKSHEET_NAME`
*   `LLM_PROVIDER`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`
*   `STYLE_DB_PATH`, `GENERATION_DB_PATH`
*   `HEALTH_HOST`, `HEALTH_PORT`
*   `LLM_TIMEOUT_SECONDS`, `MAX_RETRIES`, `RETRY_DELAY_SECONDS`
*   `MAX_URL_CONTENT_SIZE_MB`, `MAX_PDF_FILE_SIZE_MB`

### External Credentials That Must Be Supplied by the User

1.  **Telegram Bot Token**: Obtained from BotFather.
2.  **Google Service Account JSON Credentials (Base64 encoded)**: Obtained from Google Cloud Console, with access to your Google Sheet.
3.  **Google Spreadsheet ID**: The ID of your target Google Sheet.

### Limitations That Genuinely Cannot Be Tested Without External Credentials

*   **End-to-end Telegram Bot Interaction**: While handlers are unit-tested, the full interaction flow (sending messages, receiving responses) requires a live Telegram bot token.
*   **Live Ollama API Calls**: The `OllamaClient` is mocked in unit tests. Full integration with a running Ollama instance (local or remote) requires the `OLLAMA_BASE_URL` to be correctly configured and the model to be available.
*   **Live Google Sheets Writes**: The `GoogleSheetsClient` is mocked in unit tests. Actual data writing and header initialization in a Google Sheet requires valid `GOOGLE_SHEETS_CREDENTIALS_B64`, `GOOGLE_SPREADSHEET_ID`, and `GOOGLE_WORKSHEET_NAME`.
*   **Real-world URL Fetching**: The `URLExtractor`'s HTTP requests are mocked. Testing against diverse real-world URLs requires live network access.
*   **Real-world PDF Processing**: The `PDFExtractor`'s file download and `pdftotext` execution are mocked. Testing with various real PDF files requires actual file operations and the `pdftotext` utility.

The provided tests cover the logic of these integrations extensively through mocking, but actual external connectivity and data flow can only be verified with valid credentials and running services.