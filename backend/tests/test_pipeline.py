import pytest

from app.database import init_db_engine, Base, get_session_local
from app.main import (
    health_check,
    list_sample_repositories,
    execute_agent_run,
    list_agent_runs,
    get_agent_run,
    vector_search_endpoint,
    serve_unified_frontend,
)
from app.schemas import RunAgentRequest, VectorSearchRequest


@pytest.fixture(scope="module")
def db_session():
    engine = init_db_engine()
    Base.metadata.create_all(bind=engine)
    SessionLocal = get_session_local()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_health_and_samples_endpoints():
    health_data = health_check()
    assert health_data["status"] == "ok"
    assert len(health_data["agents"]) == 5

    samples_data = list_sample_repositories()
    samples = samples_data["samples"]
    assert len(samples) >= 3
    assert samples[0]["id"] == "sample:ecommerce_checkout_bug"
    assert "checkout.py" in samples[0]["files"]

    ui_resp = serve_unified_frontend()
    assert ui_resp.status_code == 200
    assert "AI Software Engineering Agent" in ui_resp.body.decode("utf-8")


def test_self_healing_multi_agent_pipeline_ecommerce(db_session):
    """
    Verify that the 5-agent LangGraph pipeline:
    1. Understands the code structure & indexes AST chunks
    2. Diagnoses the 3 root cause bugs in checkout.py
    3. Generates an initial fix in Iteration 1
    4. Runs pytest in Testing Agent, catches the remaining coupon negative clamping edge case
    5. Loops back to Code Generation Agent in Iteration 2, modifies the fix, and passes all 5 pytest unit tests
    6. Completes Code Review and generates a Pull Request
    """
    req = RunAgentRequest(
        repo_source="sample:ecommerce_checkout_bug",
        issue_description="Discount percentage is 10x too large, empty cart raises ZeroDivisionError, and coupon can make subtotal negative.",
        error_logs="ZeroDivisionError: float division by zero in calculate_average_item_price",
        llm_provider="mock",
        max_iterations=3,
        demonstrate_self_healing=True,
    )
    run = execute_agent_run(req, db=db_session)

    assert run.status == "COMPLETED"
    assert run.tests_passed is True
    # Because demonstrate_self_healing=True, Iteration 1 fails 1 edge case and Iteration 2 self-heals!
    assert run.iterations_used == 2
    assert len(run.test_history) == 2
    assert run.test_history[0]["passed"] is False
    assert run.test_history[0]["failed_count"] == 1
    assert run.test_history[1]["passed"] is True
    assert run.test_history[1]["passed_count"] == 5
    assert run.test_history[1]["failed_count"] == 0

    # Verify Code Review & Pull Request generation
    assert run.code_review["verdict"] == "APPROVED"
    assert "checkout.py" in run.pull_request["files_changed"]
    assert "-            discount_amount = gross * (item.discount_pct / 10.0)" in run.proposed_changes["unified_diff"]
    assert "+            discount_amount = gross * (item.discount_pct / 100.0)" in run.proposed_changes["unified_diff"]

    # Verify vector search works on indexed chunks
    search_res = vector_search_endpoint(
        VectorSearchRequest(run_id=run.id, query="loyalty coupon discount subtotal", top_k=3),
        db=db_session,
    )
    results = search_res["results"]
    assert len(results) > 0
    assert any("apply_loyalty_coupon" in r["symbol_name"] or "CheckoutProcessor" in r["symbol_name"] for r in results)

    # Verify run history retrieval
    fetched = get_agent_run(run.id, db=db_session)
    assert fetched.id == run.id
    all_runs = list_agent_runs(db=db_session)
    assert len(all_runs) >= 1


def test_self_healing_multi_agent_pipeline_task_queue(db_session):
    """Verify the self-healing pipeline on the second sample repo (`sample:async_task_queue_bug`)."""
    req = RunAgentRequest(
        repo_source="sample:async_task_queue_bug",
        issue_description="Mutable default tags leak, linear backoff without cap, and off-by-one retry limit.",
        error_logs="AssertionError: task.status == 'RETRYING' when attempts == max_retries",
        llm_provider="mock",
        max_iterations=3,
        demonstrate_self_healing=True,
    )
    run = execute_agent_run(req, db=db_session)

    assert run.status == "COMPLETED"
    assert run.tests_passed is True
    assert run.iterations_used == 2
    assert run.test_history[0]["passed"] is False
    assert run.test_history[1]["passed"] is True
    assert run.test_history[1]["passed_count"] == 4
    assert run.code_review["verdict"] == "APPROVED"


def test_self_healing_multi_agent_pipeline_graph_router(db_session):
    """Verify the self-healing pipeline on the 3rd CS sample repo (`sample:graph_shortest_path_bug`)."""
    req = RunAgentRequest(
        repo_source="sample:graph_shortest_path_bug",
        issue_description="Negative weights allowed in Dijkstra, unreachable returns 0.0, and start node missing from path.",
        error_logs="AssertionError: Expected path == ['A', 'B', 'C', 'D'], got ['B', 'C', 'D']",
        llm_provider="mock",
        max_iterations=3,
        demonstrate_self_healing=True,
    )
    run = execute_agent_run(req, db=db_session)

    assert run.status == "COMPLETED"
    assert run.tests_passed is True
    assert run.iterations_used == 2
    assert run.test_history[0]["passed"] is False
    assert run.test_history[1]["passed"] is True
    assert run.test_history[1]["passed_count"] == 3
    assert run.code_review["verdict"] == "APPROVED"
    assert "graph_router.py" in run.pull_request["files_changed"]


def test_custom_inline_code_sandbox_pipeline(db_session):
    """Verify running the 5-agent pipeline on custom inline Python code submitted via `custom_files`."""
    custom_files = {
        "metrics.py": (
            "def compute_average(values: list[float]) -> float:\n"
            "    total = sum(values)\n"
            "    return total / len(values)\n"
        ),
        "test_metrics.py": (
            "from metrics import compute_average\n\n"
            "def test_compute_average_non_empty():\n"
            "    assert compute_average([10.0, 20.0]) == 15.0\n\n"
            "def test_compute_average_empty_guard():\n"
            "    assert compute_average([]) == 0.0\n"
        ),
    }
    req = RunAgentRequest(
        repo_source="custom:student_metrics_sandbox",
        issue_description="compute_average([]) raises ZeroDivisionError when values list is empty.",
        error_logs="ZeroDivisionError: division by zero in compute_average",
        llm_provider="mock",
        max_iterations=2,
        demonstrate_self_healing=False,
        custom_files=custom_files,
    )
    run = execute_agent_run(req, db=db_session)
    assert run.status == "COMPLETED"
    assert run.tests_passed is True
    assert run.code_review["verdict"] == "APPROVED"
    assert "return 0.0 if len(values) == 0 else total / len(values)" in run.proposed_changes["unified_diff"]


