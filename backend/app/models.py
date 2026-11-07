from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, Float, Boolean
from sqlalchemy.types import TypeDecorator

try:
    from pgvector.sqlalchemy import Vector as PGVector
except ImportError:
    PGVector = None

from app.config import settings
from app.database import Base


class EmbeddingVectorType(TypeDecorator):
    """Uses native pgvector Vector(dim) on PostgreSQL and JSON array on SQLite."""

    impl = JSON
    cache_ok = True

    def __init__(self, dim: int = 64, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dim = dim

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and PGVector is not None:
            return dialect.type_descriptor(PGVector(self.dim))
        return dialect.type_descriptor(JSON())


def utcnow():
    return datetime.now(timezone.utc)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(String(64), primary_key=True, index=True)
    repo_source = Column(String(512), nullable=False)
    repo_name = Column(String(255), nullable=False)
    issue_description = Column(Text, nullable=True)
    error_logs = Column(Text, nullable=True)
    status = Column(String(64), default="RUNNING", nullable=False)
    llm_provider_used = Column(String(64), default="mock")
    max_iterations = Column(Integer, default=3)
    iterations_used = Column(Integer, default=0)
    tests_passed = Column(Boolean, default=False)

    # Structured outputs from the 5 agents
    code_structure = Column(JSON, nullable=True)
    root_cause_analysis = Column(JSON, nullable=True)
    proposed_changes = Column(JSON, nullable=True)
    generated_tests = Column(JSON, nullable=True)
    test_history = Column(JSON, nullable=True)
    code_review = Column(JSON, nullable=True)
    pull_request = Column(JSON, nullable=True)
    agent_timeline = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class CodeChunkEmbedding(Base):
    __tablename__ = "code_chunk_embeddings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    repo_name = Column(String(255), index=True)
    file_path = Column(String(512), nullable=False)
    symbol_name = Column(String(255), nullable=False)
    symbol_type = Column(String(64), nullable=False)  # function | class | module
    start_line = Column(Integer, default=1)
    end_line = Column(Integer, default=1)
    content = Column(Text, nullable=False)
    embedding = Column(EmbeddingVectorType(settings.EMBEDDING_DIMENSION), nullable=False)
    similarity_score = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

