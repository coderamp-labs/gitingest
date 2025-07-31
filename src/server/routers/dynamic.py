"""The dynamic router module defines handlers for dynamic path requests."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from server.server_config import get_version_info, templates

router = APIRouter()


@router.get("/{full_path:path}", include_in_schema=False)
async def catch_all(request: Request, full_path: str) -> HTMLResponse:
    """Render a page with a Git URL based on the provided path.

    This endpoint catches all GET requests with a dynamic path, constructs a Git URL
    using the ``full_path`` parameter, and renders the ``git.jinja`` template with that URL.

    Parameters
    ----------
    request : Request
        The incoming request object, which provides context for rendering the response.
    full_path : str
        The full path extracted from the URL, which is used to build the Git URL.

    Returns
    -------
    HTMLResponse
        An HTML response containing the rendered template, with the Git URL
        and other default parameters such as file size.

    """
    context = {
        "request": request,
        "repo_url": full_path,
        "default_max_file_size": 243,
    }
    context.update(get_version_info())

    return templates.TemplateResponse("git.jinja", context)
