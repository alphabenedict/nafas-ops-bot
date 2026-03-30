from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from control.db.database import get_db
from control.services.analytics import get_all_bots_stats
from control.web.auth import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="control/web/templates")


@router.get("/", response_class=HTMLResponse)
async def root(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        # Show register page if no users exist
        from control.db.models import User
        if db.query(User).count() == 0:
            return RedirectResponse("/register", status_code=302)
        return RedirectResponse("/login", status_code=302)
    return RedirectResponse("/dashboard", status_code=302)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    from control.bots.runner import is_running
    bots_stats = get_all_bots_stats(db, user.id)
    for item in bots_stats:
        item["is_running"] = is_running(item["bot"].id)

    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "user": user, "bots_stats": bots_stats},
    )
