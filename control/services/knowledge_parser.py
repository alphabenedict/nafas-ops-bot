"""
Parse uploaded knowledge sources (plain text, PDF, DOCX) into text chunks.
Chunks are ~500 characters with ~50-character overlap.
"""

import io
import re
from typing import List, Tuple

CHUNK_SIZE = 500
OVERLAP = 50


def _chunk_text(text: str, source_name: str) -> List[Tuple[str, str, int]]:
    """Split text into overlapping chunks. Returns list of (source_name, chunk_text, index)."""
    # Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []

    chunks = []
    start = 0
    idx = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end]
        if chunk.strip():
            chunks.append((source_name, chunk.strip(), idx))
            idx += 1
        start = end - OVERLAP

    return chunks


def parse_plain_text(text: str, source_name: str = "manual_text") -> List[Tuple[str, str, int]]:
    return _chunk_text(text, source_name)


def parse_pdf(file_bytes: bytes, source_name: str) -> List[Tuple[str, str, int]]:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        full_text = "\n\n".join(
            page.extract_text() or "" for page in reader.pages
        )
        return _chunk_text(full_text, source_name)
    except Exception as e:
        raise ValueError(f"Failed to parse PDF: {e}") from e


def parse_docx(file_bytes: bytes, source_name: str) -> List[Tuple[str, str, int]]:
    try:
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        full_text = "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return _chunk_text(full_text, source_name)
    except Exception as e:
        raise ValueError(f"Failed to parse DOCX: {e}") from e


def parse_upload(file_bytes: bytes, filename: str) -> List[Tuple[str, str, int]]:
    """Auto-detect format from filename and parse."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return parse_pdf(file_bytes, filename)
    elif lower.endswith(".docx"):
        return parse_docx(file_bytes, filename)
    else:
        # Treat as plain text
        return parse_plain_text(file_bytes.decode("utf-8", errors="replace"), filename)
