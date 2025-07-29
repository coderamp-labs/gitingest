"""Prometheus metrics server running on a separate port."""

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from prometheus_client import REGISTRY, generate_latest

from gitingest.utils.logging_config import get_logger

# Create a logger for this module
logger = get_logger(__name__)

# Create a separate FastAPI app for metrics
metrics_app = FastAPI(
    title="Gitingest Metrics",
    description="Prometheus metrics for Gitingest",
    docs_url=None,
    redoc_url=None,
)


@metrics_app.get("/metrics")
async def metrics() -> HTMLResponse:
    """Serve Prometheus metrics without authentication.

    This endpoint is only accessible from the local network.

    Returns
    -------
    HTMLResponse
        Prometheus metrics in text format

    """
    return HTMLResponse(
        content=generate_latest(REGISTRY),
        status_code=200,
        media_type="text/plain",
    )


def start_metrics_server(host: str = "127.0.0.1", port: int = 9090) -> None:
    """Start the metrics server on a separate port.

    Parameters
    ----------
    host : str
        The host to bind to (default: 127.0.0.1 for local network only)
    port : int
        The port to bind to (default: 9090)

    Returns
    -------
    None

    """
    logger.info("Starting metrics server", extra={"host": host, "port": port})

    # Configure uvicorn to suppress startup messages to avoid duplicates
    # since the main server already shows similar messages
    uvicorn.run(
        metrics_app,
        host=host,
        port=port,
        log_config=None,  # Disable uvicorn's default logging config
        access_log=False,  # Disable access logging for metrics server
        # Suppress uvicorn's startup messages by setting log level higher
        log_level="warning",
    )
