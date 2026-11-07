from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import List
import uuid

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config import settings, SAMPLE_REPOS_DIR, BASE_DIR
from app.database import Base, init_db_engine, get_db, is_pgvector_active
from app.models import AgentRun
from app.schemas import RunAgentRequest, AgentRunResponse, VectorSearchRequest
from app.services.llm_service import resolve_llm_provider
from app.services.vector_store import search_similar_chunks
from app.agents.graph import swe_agent_graph


@asynccontextmanager
async def lifespan(_app: FastAPI):
    engine = init_db_engine()
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Multi-Agent AI Software Engineering System built with LangGraph, FastAPI, and pgvector. "
        "Includes Code Understanding, Debugging, Code Generation, Testing (Self-Healing Loop), and Code Review Agents."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


SAMPLE_PRESETS = [
    {
        "id": "sample:ecommerce_checkout_bug",
        "name": "E-Commerce Checkout Service (3 Compounding Bugs)",
        "repo_source": "sample:ecommerce_checkout_bug",
        "description": "Contains a 10x percentage discount divisor bug, an unguarded ZeroDivisionError on empty carts, and negative subtotal coupon overflow.",
        "issue_description": (
            "Customers applying a 20% item discount are getting 200% deducted from their item total, "
            "empty carts crash the checkout service with ZeroDivisionError, and applying a $50 VIP coupon "
            "to a $30 order produces a -$20.00 total."
        ),
        "error_logs": (
            "Traceback (most recent call last):\n"
            "  File \"checkout.py\", line 60, in process_checkout\n"
            "    avg_unit_price = self.calculate_average_item_price(items)\n"
            "  File \"checkout.py\", line 39, in calculate_average_item_price\n"
            "    return round(total_cost / total_units, 2)\n"
            "ZeroDivisionError: float division by zero\n\n"
            "AssertionError in checkout subtotal: expected 160.0 for 20% discount on $200.0, got -200.0"
        ),
    },
    {
        "id": "sample:async_task_queue_bug",
        "name": "Distributed Task Queue & Retry Scheduler (3 Bugs)",
        "repo_source": "sample:async_task_queue_bug",
        "description": "Contains a mutable default argument leak across TaskRecord instances, linear instead of exponential retry backoff without max_delay cap, and an off-by-one dead-letter queue threshold.",
        "issue_description": (
            "Task tags added to one TaskRecord appear on newly created tasks, retry backoff delays grow "
            "linearly instead of exponentially and exceed max_delay, and failing tasks retry 4 times when max_retries=3."
        ),
        "error_logs": (
            "AssertionError: TaskRecord('task-2') unexpectedly has tags=['urgent'] from previous task!\n"
            "File \"task_queue.py\", line 38, in compute_backoff\n"
            "  Expected exponential backoff 8.0s on attempt 3 and max_delay cap 10.0s on attempt 4, got 16.0s.\n"
            "File \"task_queue.py\", line 49, in record_failure\n"
            "  Expected status == 'DEAD_LETTER' on attempt 3 (max_retries=3), got 'RETRYING'."
        ),
    },
    {
        "id": "sample:graph_shortest_path_bug",
        "name": "CS Graph Shortest-Path Router — Dijkstra (3 Bugs)",
        "repo_source": "sample:graph_shortest_path_bug",
        "description": "Contains unvalidated negative edge weights in Dijkstra's algorithm, unreachable targets returning 0.0 instead of inf, and missing start node in path reconstruction.",
        "issue_description": (
            "Dijkstra shortest_path accepts negative edge weights without raising ValueError, "
            "returns distance 0.0 instead of float('inf') when the destination is unreachable, "
            "and omits the start vertex from the reconstructed shortest path list."
        ),
        "error_logs": (
            "AssertionError in test_dijkstra_shortest_path_and_route:\n"
            "  File \"graph_router.py\", line 59, in shortest_path\n"
            "    Expected path == ['A', 'B', 'C', 'D'], got ['B', 'C', 'D']\n"
            "AssertionError in test_unreachable_destination_returns_infinity:\n"
            "    Expected distance == inf, got 0.0"
        ),
    },
]


@app.get("/api/health")
def health_check():
    provider, _ = resolve_llm_provider(settings.LLM_PROVIDER)
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database_backend": "postgresql+pgvector" if is_pgvector_active() else "sqlite+local_vector",
        "default_llm_provider": provider,
        "agents": [
            "Code Understanding Agent",
            "Debugging Agent",
            "Code Generation Agent",
            "Testing Agent",
            "Code Review Agent",
        ],
    }


@app.get("/api/samples")
def list_sample_repositories():
    enriched = []
    for preset in SAMPLE_PRESETS:
        folder_name = preset["repo_source"].split("sample:", 1)[1]
        folder_path = SAMPLE_REPOS_DIR / folder_name
        files = {}
        if folder_path.exists():
            for fp in sorted(folder_path.glob("*.py")):
                files[fp.name] = fp.read_text(encoding="utf-8", errors="replace")
        enriched.append({**preset, "files": files})
    return {"samples": enriched}


@app.post("/api/runs", response_model=AgentRunResponse)
def execute_agent_run(req: RunAgentRequest, db: Session = Depends(get_db)):
    run_id = f"run-{uuid.uuid4().hex[:10]}"
    provider, resolved_key = resolve_llm_provider(req.llm_provider, req.api_key)

    initial_run = AgentRun(
        id=run_id,
        repo_source=req.repo_source,
        repo_name=req.repo_source.split(":")[-1].split("/")[-1],
        issue_description=req.issue_description,
        error_logs=req.error_logs,
        status="RUNNING",
        llm_provider_used=provider,
        max_iterations=req.max_iterations,
    )
    db.add(initial_run)
    db.commit()

    try:
        initial_state = {
            "run_id": run_id,
            "repo_source": req.repo_source,
            "issue_description": req.issue_description or "",
            "error_logs": req.error_logs or "",
            "llm_provider": provider,
            "api_key": resolved_key,
            "github_token": req.github_token or settings.GITHUB_TOKEN,
            "create_github_pr": req.create_github_pr,
            "max_iterations": req.max_iterations,
            "demonstrate_self_healing": req.demonstrate_self_healing,
            "custom_files": req.custom_files,
        }

        final_state = swe_agent_graph.invoke(initial_state)

        initial_run.repo_name = final_state.get("repo_name", initial_run.repo_name)
        initial_run.status = "COMPLETED"
        initial_run.iterations_used = int(final_state.get("iteration", 1))
        initial_run.tests_passed = bool(final_state.get("tests_passed", False))
        initial_run.code_structure = final_state.get("code_structure")
        initial_run.root_cause_analysis = final_state.get("root_cause_analysis")
        initial_run.proposed_changes = final_state.get("proposed_changes")
        initial_run.generated_tests = final_state.get("generated_tests")
        initial_run.test_history = final_state.get("test_history")
        initial_run.code_review = final_state.get("code_review")
        initial_run.pull_request = final_state.get("pull_request")
        initial_run.agent_timeline = final_state.get("agent_timeline")
        initial_run.completed_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(initial_run)
        return initial_run
    except Exception as exc:
        initial_run.status = "FAILED"
        initial_run.completed_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=400, detail=f"Agent pipeline execution failed: {exc}") from exc


@app.get("/api/runs", response_model=List[AgentRunResponse])
def list_agent_runs(db: Session = Depends(get_db)):
    runs = db.query(AgentRun).order_by(AgentRun.created_at.desc()).limit(25).all()
    return runs


@app.get("/api/runs/{run_id}", response_model=AgentRunResponse)
def get_agent_run(run_id: str, db: Session = Depends(get_db)):
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return run


@app.post("/api/vector-search")
def vector_search_endpoint(req: VectorSearchRequest, db: Session = Depends(get_db)):
    results = search_similar_chunks(
        db=db,
        query=req.query,
        run_id=req.run_id,
        top_k=req.top_k,
    )
    return {
        "query": req.query,
        "run_id": req.run_id,
        "backend": "pgvector" if is_pgvector_active() else "local_vector",
        "results": results,
    }


# Unified Full-Stack Frontend Serving (serves Vite build if present, otherwise built-in static SPA)
FRONTEND_DIST_DIR = BASE_DIR / "frontend" / "dist"
STATIC_INDEX_FILE = Path(__file__).resolve().parent / "static" / "index.html"

if (FRONTEND_DIST_DIR / "assets").exists():
    app.mount(
        "/assets",
        StaticFiles(directory=str(FRONTEND_DIST_DIR / "assets")),
        name="frontend_assets",
    )


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def serve_unified_frontend():
    dist_index = FRONTEND_DIST_DIR / "index.html"
    if dist_index.exists():
        return FileResponse(str(dist_index))
    if STATIC_INDEX_FILE.exists():
        return HTMLResponse(STATIC_INDEX_FILE.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>AI Software Engineering Agent API is running. Visit /docs</h1>")


