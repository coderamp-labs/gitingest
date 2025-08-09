"""Main module for the FastAPI application."""

from __future__ import annotations

import os
import threading
from pathlib import Path

import sentry_sdk
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from starlette.middleware.trustedhost import TrustedHostMiddleware

# Import logging configuration first to intercept all logging
from gitingest.utils.logging_config import get_logger
from server.metrics_server import start_metrics_server
from server.routers import dynamic, index, ingest
from server.server_config import get_version_info, templates
from server.server_utils import limiter, rate_limit_exception_handler

# Load environment variables from .env file
load_dotenv()

# Initialize logger for this module
logger = get_logger(__name__)

# Initialize Sentry SDK if enabled
if os.getenv("GITINGEST_SENTRY_ENABLED") is not None:
    sentry_dsn = os.getenv("GITINGEST_SENTRY_DSN")

    # Only initialize Sentry if DSN is provided
    if sentry_dsn:
        # Configure Sentry options from environment variables
        traces_sample_rate = float(os.getenv("GITINGEST_SENTRY_TRACES_SAMPLE_RATE", "1.0"))
        profile_session_sample_rate = float(os.getenv("GITINGEST_SENTRY_PROFILE_SESSION_SAMPLE_RATE", "1.0"))
        profile_lifecycle_raw = os.getenv("GITINGEST_SENTRY_PROFILE_LIFECYCLE", "trace")
        profile_lifecycle = profile_lifecycle_raw if profile_lifecycle_raw in ("manual", "trace") else "trace"
        send_default_pii = os.getenv("GITINGEST_SENTRY_SEND_DEFAULT_PII", "true").lower() == "true"
        sentry_environment = os.getenv("GITINGEST_SENTRY_ENVIRONMENT", "")

        sentry_sdk.init(
            dsn=sentry_dsn,
            # Add data like request headers and IP for users
            send_default_pii=send_default_pii,
            # Set traces_sample_rate to capture transactions for tracing
            traces_sample_rate=traces_sample_rate,
            # Set profile_session_sample_rate to profile sessions
            profile_session_sample_rate=profile_session_sample_rate,
            # Set profile_lifecycle to automatically run the profiler
            profile_lifecycle=profile_lifecycle,
            # Set environment name
            environment=sentry_environment,
        )

# Initialize the FastAPI application
app = FastAPI(docs_url=None, redoc_url=None)
app.state.limiter = limiter

# Register the custom exception handler for rate limits
app.add_exception_handler(RateLimitExceeded, rate_limit_exception_handler)

# Start metrics server in a separate thread if enabled
if os.getenv("GITINGEST_METRICS_ENABLED") is not None:
    metrics_host = os.getenv("GITINGEST_METRICS_HOST", "127.0.0.1")
    metrics_port = int(os.getenv("GITINGEST_METRICS_PORT", "9090"))
    metrics_thread = threading.Thread(
        target=start_metrics_server,
        args=(metrics_host, metrics_port),
        daemon=True,
    )
    metrics_thread.start()


# Mount static files dynamically to serve CSS, JS, and other static assets
static_dir = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# Fetch allowed hosts from the environment or use the default values
allowed_hosts = os.getenv("ALLOWED_HOSTS")
if allowed_hosts:
    allowed_hosts = allowed_hosts.split(",")
else:
    # Define the default allowed hosts for the application
    default_allowed_hosts = ["gitingest.com", "*.gitingest.com", "localhost", "127.0.0.1"]
    allowed_hosts = default_allowed_hosts

# Add middleware to enforce allowed hosts
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint to verify that the server is running.

    **Returns**

    - **dict[str, str]**: A JSON object with a "status" key indicating the server's health status.

    """
    return {"status": "healthy"}


@app.head("/", include_in_schema=False)
async def head_root() -> HTMLResponse:
    """Respond to HTTP HEAD requests for the root URL.

    **This endpoint mirrors the headers and status code of the index page**
    for HTTP HEAD requests, providing a lightweight way to check if the server
    is responding without downloading the full page content.

    **Returns**

    - **HTMLResponse**: An empty HTML response with appropriate headers

    """
    return HTMLResponse(content=None, headers={"content-type": "text/html; charset=utf-8"})


@app.get("/robots.txt", include_in_schema=False)
async def robots() -> FileResponse:
    """Serve the robots.txt file to guide search engine crawlers.

    **This endpoint serves the ``robots.txt`` file located in the static directory**
    to provide instructions to search engine crawlers about which parts of the site
    they should or should not index.

    **Returns**

    - **FileResponse**: The ``robots.txt`` file located in the static directory

    """
    return FileResponse("static/robots.txt")


@app.get("/llms.txt")
async def llm_txt() -> FileResponse:
    """Serve the llm.txt file to provide information about the site to LLMs.

    **This endpoint serves the ``llms.txt`` file located in the static directory**
    to provide information about the site to Large Language Models (LLMs)
    and other AI systems that may be crawling the site.

    **Returns**

    - **FileResponse**: The ``llms.txt`` file located in the static directory

    """
    return FileResponse("static/llms.txt")


@app.get("/docs", response_class=HTMLResponse, include_in_schema=False)
async def custom_swagger_ui(request: Request) -> HTMLResponse:
    """Serve custom Swagger UI documentation.

    **This endpoint serves a custom Swagger UI interface**
    for the API documentation, providing an interactive way to explore
    and test the available endpoints.

    **Parameters**

    - **request** (`Request`): The incoming HTTP request

    **Returns**

    - **HTMLResponse**: Custom Swagger UI documentation page

    """
    context = {"request": request}
    context.update(get_version_info())
    return templates.TemplateResponse("swagger_ui.jinja", context)


@app.get("/api", include_in_schema=True)
def openapi_json_get() -> JSONResponse:
    """Return the OpenAPI schema.

    **This endpoint returns the OpenAPI schema (openapi.json)**
    that describes the API structure, endpoints, and data models
    for documentation and client generation purposes.

    **Returns**

    - **JSONResponse**: The OpenAPI schema as JSON

    """
    return JSONResponse(app.openapi())


@app.api_route("/api", methods=["POST", "PUT", "DELETE", "OPTIONS", "HEAD"], include_in_schema=False)
@app.api_route("/api/", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"], include_in_schema=False)
def openapi_json() -> JSONResponse:
    """Return the OpenAPI schema for various HTTP methods.

    **This endpoint returns the OpenAPI schema (openapi.json)**
    for multiple HTTP methods, providing API documentation
    for clients that may use different request methods.

    **Returns**

    - **JSONResponse**: The OpenAPI schema as JSON

    """
    return JSONResponse(app.openapi())


# Include routers for modular endpoints
app.include_router(index)
app.include_router(ingest)
app.include_router(dynamic)
