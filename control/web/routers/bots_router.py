import httpx
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from control.db.database import get_db
from control.db.models import Bot, KnowledgeChunk
from control.services.analytics import get_bot_stats, get_contact_list
from control.web.auth import get_current_user

router = APIRouter(prefix="/bots")
templates = Jinja2Templates(directory="control/web/templates")


async def _validate_telegram_token(token: str) -> dict | None:
    """Call Telegram getMe to validate a bot token. Returns bot info or None."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            data = resp.json()
            if data.get("ok"):
                return data["result"]
    except Exception:
        pass
    return None


@router.get("/new", response_class=HTMLResponse)
async def new_bot_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("bot_create.html", {"request": request, "user": user, "error": None})


@router.post("/new", response_class=HTMLResponse)
async def create_bot(
    request: Request,
    name: str = Form(...),
    telegram_token: str = Form(...),
    role_description: str = Form(""),
    personality: str = Form(""),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    # Validate token
    bot_info = await _validate_telegram_token(telegram_token)
    if not bot_info:
        return templates.TemplateResponse(
            "bot_create.html",
            {"request": request, "user": user, "error": "Token Telegram tidak valid. Periksa kembali."},
        )

    # Check duplicate token
    existing = db.query(Bot).filter(Bot.telegram_token == telegram_token).first()
    if existing:
        return templates.TemplateResponse(
            "bot_create.html",
            {"request": request, "user": user, "error": "Token ini sudah digunakan oleh bot lain."},
        )

    bot = Bot(
        owner_id=user.id,
        name=name,
        telegram_token=telegram_token,
        role_description=role_description,
        personality=personality,
        is_active=False,
    )
    db.add(bot)
    db.commit()
    db.refresh(bot)
    return RedirectResponse(f"/bots/{bot.id}", status_code=302)


@router.get("/{bot_id}", response_class=HTMLResponse)
async def bot_detail(request: Request, bot_id: str, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    bot = db.query(Bot).filter(
        Bot.id == bot_id,
        or_(Bot.owner_id == user.id, Bot.is_system == True),
    ).first()
    if not bot:
        return RedirectResponse("/dashboard", status_code=302)

    from control.bots.runner import is_running
    from config import SHEET_ID
    stats = get_bot_stats(db, bot_id)
    contacts_data = get_contact_list(db, bot_id, page=1, per_page=10)
    knowledge = db.query(KnowledgeChunk).filter(KnowledgeChunk.bot_id == bot_id).all()

    # Build connector info for the system NafasOps bot
    connectors = None
    if bot.is_system:
        sheet_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}" if SHEET_ID else None
        connectors = {
            "google_sheets": {
                "sheet_id": SHEET_ID,
                "url": sheet_url,
                "connected": bool(SHEET_ID),
            },
            "openai": {"connected": True, "model": "GPT-4o Mini"},
        }

    return templates.TemplateResponse(
        "bot_detail.html",
        {
            "request": request,
            "user": user,
            "bot": bot,
            "stats": stats,
            "contacts_data": contacts_data,
            "knowledge": knowledge,
            "is_running": is_running(bot_id),
            "connectors": connectors,
        },
    )


@router.get("/{bot_id}/edit", response_class=HTMLResponse)
async def edit_bot_page(request: Request, bot_id: str, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    bot = db.query(Bot).filter(Bot.id == bot_id, Bot.owner_id == user.id).first()
    if not bot or bot.is_system:
        return RedirectResponse("/dashboard", status_code=302)
    from control.bots.runner import is_running as _is_running
    return templates.TemplateResponse("bot_edit.html", {"request": request, "user": user, "bot": bot, "error": None, "is_running": _is_running(bot_id)})


@router.post("/{bot_id}/edit", response_class=HTMLResponse)
async def edit_bot_submit(
    request: Request,
    bot_id: str,
    name: str = Form(...),
    role_description: str = Form(""),
    personality: str = Form(""),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    bot = db.query(Bot).filter(Bot.id == bot_id, Bot.owner_id == user.id).first()
    if not bot or bot.is_system:
        return RedirectResponse("/dashboard", status_code=302)
    bot.name = name
    bot.role_description = role_description
    bot.personality = personality
    db.commit()
    return RedirectResponse(f"/bots/{bot_id}", status_code=302)


@router.post("/{bot_id}/activate")
async def activate_bot(request: Request, bot_id: str, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    bot = db.query(Bot).filter(Bot.id == bot_id, Bot.owner_id == user.id).first()
    if not bot:
        return RedirectResponse("/dashboard", status_code=302)

    from control.bots.runner import is_running, start_tenant_bot_by_id
    import asyncio
    if not is_running(bot_id):
        bot.is_active = True
        db.commit()
        asyncio.create_task(start_tenant_bot_by_id(bot_id))

    return RedirectResponse(f"/bots/{bot_id}", status_code=302)


@router.post("/{bot_id}/deactivate")
async def deactivate_bot(request: Request, bot_id: str, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    bot = db.query(Bot).filter(Bot.id == bot_id, Bot.owner_id == user.id).first()
    if not bot or bot.is_system:
        return RedirectResponse("/dashboard", status_code=302)

    from control.bots.runner import is_running, stop_tenant_bot_by_id
    import asyncio
    if is_running(bot_id):
        bot.is_active = False
        db.commit()
        asyncio.create_task(stop_tenant_bot_by_id(bot_id))

    return RedirectResponse(f"/bots/{bot_id}", status_code=302)


@router.post("/{bot_id}/delete")
async def delete_bot(request: Request, bot_id: str, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    bot = db.query(Bot).filter(Bot.id == bot_id, Bot.owner_id == user.id).first()
    if not bot or bot.is_system:
        return RedirectResponse("/dashboard", status_code=302)

    from control.bots.runner import is_running, stop_tenant_bot_by_id
    import asyncio
    if is_running(bot_id):
        asyncio.create_task(stop_tenant_bot_by_id(bot_id))

    db.delete(bot)
    db.commit()
    return RedirectResponse("/dashboard", status_code=302)
