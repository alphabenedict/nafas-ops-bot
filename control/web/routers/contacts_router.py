from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from control.db.database import get_db
from control.db.models import Bot, Contact
from control.services.analytics import get_contact_list, get_conversation, get_latest_summary
from control.web.auth import get_current_user

router = APIRouter(prefix="/bots")
templates = Jinja2Templates(directory="control/web/templates")


@router.get("/{bot_id}/contacts", response_class=HTMLResponse)
async def contacts_list(
    request: Request, bot_id: str, page: int = 1, db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    bot = db.query(Bot).filter(Bot.id == bot_id, Bot.owner_id == user.id).first()
    if not bot:
        return RedirectResponse("/dashboard", status_code=302)

    contacts_data = get_contact_list(db, bot_id, page=page, per_page=20)
    return templates.TemplateResponse(
        "contacts.html",
        {"request": request, "user": user, "bot": bot, "contacts_data": contacts_data},
    )


@router.get("/{bot_id}/contacts/{contact_id}", response_class=HTMLResponse)
async def conversation_view(
    request: Request, bot_id: str, contact_id: str, db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    bot = db.query(Bot).filter(Bot.id == bot_id, Bot.owner_id == user.id).first()
    if not bot:
        return RedirectResponse("/dashboard", status_code=302)

    contact = db.query(Contact).filter(
        Contact.id == contact_id, Contact.bot_id == bot_id
    ).first()
    if not contact:
        return RedirectResponse(f"/bots/{bot_id}/contacts", status_code=302)

    messages = get_conversation(db, contact_id)
    summary = get_latest_summary(db, contact_id)

    return templates.TemplateResponse(
        "conversation.html",
        {
            "request": request,
            "user": user,
            "bot": bot,
            "contact": contact,
            "messages": messages,
            "summary": summary,
        },
    )


@router.get("/{bot_id}/contacts/export/csv")
async def export_contacts_csv(request: Request, bot_id: str, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    bot = db.query(Bot).filter(Bot.id == bot_id, Bot.owner_id == user.id).first()
    if not bot:
        return RedirectResponse("/dashboard", status_code=302)

    contacts = db.query(Contact).filter(Contact.bot_id == bot_id).all()

    def generate():
        yield "telegram_id,username,first_name,last_name,first_seen,last_seen\n"
        for c in contacts:
            yield (
                f"{c.telegram_id},"
                f"{c.username or ''},"
                f"{c.first_name or ''},"
                f"{c.last_name or ''},"
                f"{c.first_seen_at.isoformat()},"
                f"{c.last_seen_at.isoformat()}\n"
            )

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=contacts_{bot_id[:8]}.csv"},
    )
