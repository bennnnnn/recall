from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.content.legal import (
    PRIVACY_POLICY_MD,
    TERMS_OF_SERVICE_MD,
    markdown_to_html,
)

router = APIRouter(prefix="/legal", tags=["legal"])


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_policy() -> HTMLResponse:
    return HTMLResponse(
        markdown_to_html(PRIVACY_POLICY_MD, page_title="Recall Privacy Policy"),
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/terms", response_class=HTMLResponse)
async def terms_of_service() -> HTMLResponse:
    return HTMLResponse(
        markdown_to_html(TERMS_OF_SERVICE_MD, page_title="Recall Terms of Service"),
        headers={"Cache-Control": "public, max-age=3600"},
    )
