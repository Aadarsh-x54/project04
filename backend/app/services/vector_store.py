import hashlib
import math
import re
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import is_pgvector_active
from app.models import CodeChunkEmbedding


TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def compute_code_embedding(text_content: str, dim: int = settings.EMBEDDING_DIMENSION) -> List[float]:
    """
    Generate a normalized semantic/lexical feature-hashed embedding vector of length `dim`.
    Splits camelCase and snake_case identifiers so related code symbols and error logs
    map closely in vector space without requiring external network calls.
    """
    vec = [0.0] * dim
    raw_tokens = TOKEN_RE.findall(text_content)
    expanded_tokens: List[str] = []
    for tok in raw_tokens:
        expanded_tokens.append(tok.lower())
        # Split snake_case and camelCase
        parts = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", tok).lower().split("_")
        for p in parts:
            if len(p) > 1:
                expanded_tokens.append(p)

    if not expanded_tokens:
        vec[0] = 1.0
        return vec

    for tok in expanded_tokens:
        digest = hashlib.sha256(tok.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if (digest[4] % 2 == 0) else -1.0
        vec[idx] += sign

    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [round(v / norm, 6) for v in vec]
    return vec


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a * a for a in v1))
    n2 = math.sqrt(sum(b * b for b in v2))
    if n1 == 0 or n2 == 0:
        return 0.0
    return float(dot / (n1 * n2))


def index_code_chunks(
    db: Session,
    run_id: str,
    repo_name: str,
    chunks: List[Dict[str, Any]],
) -> int:
    """Compute embeddings for all AST chunks and persist them in PostgreSQL (pgvector) or local store."""
    records = []
    for chunk in chunks:
        rich_text = f"{chunk['file_path']} {chunk['symbol_name']} {chunk['symbol_type']}\n{chunk['content']}"
        emb = compute_code_embedding(rich_text)
        records.append(
            CodeChunkEmbedding(
                run_id=run_id,
                repo_name=repo_name,
                file_path=chunk["file_path"],
                symbol_name=chunk["symbol_name"],
                symbol_type=chunk["symbol_type"],
                start_line=chunk.get("start_line", 1),
                end_line=chunk.get("end_line", 1),
                content=chunk["content"],
                embedding=emb,
            )
        )
    if records:
        db.add_all(records)
        db.commit()
    return len(records)


def search_similar_chunks(
    db: Session,
    query: str,
    run_id: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search code chunks by vector similarity.
    Uses native pgvector `<=>` cosine distance when connected to PostgreSQL,
    or exact cosine similarity calculation when using local SQLite fallback.
    """
    query_vec = compute_code_embedding(query)

    if is_pgvector_active():
        try:
            vec_literal = "[" + ",".join(str(x) for x in query_vec) + "]"
            if run_id:
                sql = text(
                    """
                    SELECT file_path, symbol_name, symbol_type, start_line, end_line, content,
                           1 - (embedding <=> CAST(:qvec AS vector)) AS score
                    FROM code_chunk_embeddings
                    WHERE run_id = :run_id
                    ORDER BY embedding <=> CAST(:qvec AS vector)
                    LIMIT :top_k
                    """
                )
                rows = db.execute(sql, {"qvec": vec_literal, "run_id": run_id, "top_k": top_k}).mappings().all()
            else:
                sql = text(
                    """
                    SELECT file_path, symbol_name, symbol_type, start_line, end_line, content,
                           1 - (embedding <=> CAST(:qvec AS vector)) AS score
                    FROM code_chunk_embeddings
                    ORDER BY embedding <=> CAST(:qvec AS vector)
                    LIMIT :top_k
                    """
                )
                rows = db.execute(sql, {"qvec": vec_literal, "top_k": top_k}).mappings().all()

            return [
                {
                    "file_path": r["file_path"],
                    "symbol_name": r["symbol_name"],
                    "symbol_type": r["symbol_type"],
                    "start_line": r["start_line"],
                    "end_line": r["end_line"],
                    "content": r["content"],
                    "similarity": round(float(r["score"] or 0.0), 4),
                    "backend": "pgvector",
                }
                for r in rows
            ]
        except Exception:
            pass

    q = db.query(CodeChunkEmbedding)
    if run_id:
        q = q.filter(CodeChunkEmbedding.run_id == run_id)
    candidates = q.all()

    scored = []
    for item in candidates:
        emb = list(item.embedding) if item.embedding else []
        sim = cosine_similarity(query_vec, emb)
        scored.append(
            {
                "file_path": item.file_path,
                "symbol_name": item.symbol_name,
                "symbol_type": item.symbol_type,
                "start_line": item.start_line,
                "end_line": item.end_line,
                "content": item.content,
                "similarity": round(sim, 4),
                "backend": "local_vector",
            }
        )
    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:top_k]

