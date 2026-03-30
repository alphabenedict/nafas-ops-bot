from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from control.db.database import get_db
from control.db.models import User
from control.web.auth import (
    clear_session_cookie,
    create_user,
    get_current_user,
    set_session_cookie,
    verify_password,
)

router = APIRouter()
templates = Jinja2Templates(directory="control/web/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    if get_current_user(request, db):
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Email atau password salah."}
        )
    response = RedirectResponse("/dashboard", status_code=302)
    set_session_cookie(response, user.id)
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=302)
    clear_session_cookie(response)
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, db: Session = Depends(get_db)):
    # Only show registration if no users exist yet (first-run setup)
    user_count = db.query(User).count()
    if user_count > 0:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("register.html", {"request": request, "error": None})


@router.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user_count = db.query(User).count()
    if user_count > 0:
        return RedirectResponse("/login", status_code=302)
    user = create_user(db, email, password, is_admin=True)
    response = RedirectResponse("/dashboard", status_code=302)
    set_session_cookie(response, user.id)
    return response
