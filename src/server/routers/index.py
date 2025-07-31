"""Module defining the FastAPI router for the home page of the application."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from server.server_config import EXAMPLE_REPOS, get_version_info, templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home(request: Request) -> HTMLResponse:
    """Render the home page with example repositories and default parameters.

    This endpoint serves the home page of the application, rendering the ``index.jinja`` template
    and providing it with a list of example repositories and default file size values.

    Parameters
    ----------
    request : Request
        The incoming request object, which provides context for rendering the response.

    Returns
    -------
    HTMLResponse
        An HTML response containing the rendered home page template, with example repositories
        and other default parameters such as file size.

    """
    context = {
        "request": request,
        "examples": EXAMPLE_REPOS,
        "default_max_file_size": 243,
    }
    context.update(get_version_info())

    return templates.TemplateResponse("index.jinja", context)
