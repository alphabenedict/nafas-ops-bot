"""
Simple keyword-based RAG search over knowledge chunks.
Returns the most relevant chunks for a given query using TF-IDF-style scoring.
"""

import math
import re
from collections import Counter
from typing import List

from sqlalchemy.orm import Session

from control.db.models import KnowledgeChunk


def _tokenize(text: str) -> List[str]:
    return re.findall(r"\b\w+\b", text.lower())


def _score(query_tokens: List[str], chunk_text: str) -> float:
    chunk_tokens = _tokenize(chunk_text)
    if not chunk_tokens:
        return 0.0
    chunk_freq = Counter(chunk_tokens)
    total = len(chunk_tokens)
    score = 0.0
    for token in set(query_tokens):
        tf = chunk_freq.get(token, 0) / total
        # simple IDF approximation: log(1 + 1/tf) gives higher weight to rare tokens
        idf = math.log(1 + 1 / (tf + 1e-9))
        score += tf * idf
    return score


def search_knowledge(db: Session, bot_id: str, query: str, top_k: int = 3) -> str:
    """Return the top_k most relevant knowledge chunks as a single string."""
    chunks: List[KnowledgeChunk] = (
        db.query(KnowledgeChunk).filter(KnowledgeChunk.bot_id == bot_id).all()
    )
    if not chunks:
        return ""

    query_tokens = _tokenize(query)
    if not query_tokens:
        return ""

    scored = [(c, _score(query_tokens, c.chunk_text)) for c in chunks]
    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:top_k]

    # Filter out chunks with zero relevance
    relevant = [c for c, s in top if s > 0]
    if not relevant:
        return ""

    return "\n\n".join(c.chunk_text for c in relevant)
