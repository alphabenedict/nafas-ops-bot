from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from control.db.database import get_db
from control.db.models import Bot, KnowledgeChunk
from control.services.knowledge_parser import parse_plain_text, parse_upload
from control.web.auth import get_current_user

router = APIRouter(prefix="/bots")


@router.post("/{bot_id}/knowledge/text")
async def add_text_knowledge(
    request: Request,
    bot_id: str,
    source_name: str = Form("manual_text"),
    content: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    bot = db.query(Bot).filter(Bot.id == bot_id, Bot.owner_id == user.id).first()
    if not bot:
        return RedirectResponse("/dashboard", status_code=302)

    chunks = parse_plain_text(content, source_name or "manual_text")
    for src, text, idx in chunks:
        db.add(KnowledgeChunk(bot_id=bot_id, source_name=src, chunk_text=text, chunk_index=idx))
    db.commit()
    return RedirectResponse(f"/bots/{bot_id}", status_code=302)


@router.post("/{bot_id}/knowledge/upload")
async def upload_knowledge_file(
    request: Request,
    bot_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    bot = db.query(Bot).filter(Bot.id == bot_id, Bot.owner_id == user.id).first()
    if not bot:
        return RedirectResponse("/dashboard", status_code=302)

    file_bytes = await file.read()
    try:
        chunks = parse_upload(file_bytes, file.filename or "upload")
    except ValueError as e:
        return RedirectResponse(f"/bots/{bot_id}?error={e}", status_code=302)

    for src, text, idx in chunks:
        db.add(KnowledgeChunk(bot_id=bot_id, source_name=src, chunk_text=text, chunk_index=idx))
    db.commit()
    return RedirectResponse(f"/bots/{bot_id}", status_code=302)


@router.post("/{bot_id}/knowledge/{chunk_id}/delete")
async def delete_knowledge_chunk(
    request: Request, bot_id: str, chunk_id: str, db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    bot = db.query(Bot).filter(Bot.id == bot_id, Bot.owner_id == user.id).first()
    if not bot:
        return RedirectResponse("/dashboard", status_code=302)

    chunk = db.query(KnowledgeChunk).filter(
        KnowledgeChunk.id == chunk_id, KnowledgeChunk.bot_id == bot_id
    ).first()
    if chunk:
        db.delete(chunk)
        db.commit()
    return RedirectResponse(f"/bots/{bot_id}", status_code=302)
