"""
View routes for the web application.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter()

# Templates will be set during app initialization
templates = None


def get_templates():
    """Get the templates object."""
    if templates is None:
        raise RuntimeError("Templates not initialized")
    return templates


def init_templates(templates_dir: Path):
    """Initialize the templates object."""
    global templates
    templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, templates=Depends(get_templates)):
    """Render the index page."""
    return templates.TemplateResponse("index.html", {"request": request})
