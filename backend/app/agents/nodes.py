from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Dict, Any

from app.agents.state import SWEAgentState
from app.database import get_session_local
from app.services.repo_service import prepare_workspace, analyze_repository, compute_unified_diff
from app.services.vector_store import index_code_chunks, search_similar_chunks
from app.services.llm_service import (
    diagnose_root_cause,
    generate_code_fix,
    generate_unit_tests,
    review_code_changes,
)
from app.services.test_runner import apply_files_to_workspace, run_pytest_in_workspace
from app.services.github_service import build_pull_request_payload


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def code_understanding_node(state: SWEAgentState) -> Dict[str, Any]:
    """
    Agent 1: Code Understanding Agent
    - Clones or copies the target repository into an isolated workspace
    - Parses AST across files to extract classes, functions, imports, and static smell warnings
    - Indexes code chunks into PostgreSQL + pgvector (or local fallback vector store)
    - Performs semantic similarity search to locate relevant symbols
    """
    t0 = time.perf_counter()
    run_id = state["run_id"]
    repo_source = state["repo_source"]

    workspace_path, repo_name = prepare_workspace(
        run_id,
        repo_source,
        custom_files=state.get("custom_files"),
    )
    analysis = analyze_repository(workspace_path)

    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        chunks_indexed = index_code_chunks(
            db=db,
            run_id=run_id,
            repo_name=repo_name,
            chunks=analysis["chunks"],
        )
        search_query = (
            f"{state.get('issue_description', '')}\n{state.get('error_logs', '')}".strip()
            or f"{repo_name} bug error exception calculation"
        )
        relevant_chunks = search_similar_chunks(
            db=db,
            query=search_query,
            run_id=run_id,
            top_k=6,
        )
    finally:
        db.close()

    duration_ms = round((time.perf_counter() - t0) * 1000, 1)
    code_structure = {
        "repo_name": repo_name,
        "total_files": analysis["total_files"],
        "total_lines": analysis["total_lines"],
        "chunks_indexed": chunks_indexed,
        "vector_backend": relevant_chunks[0]["backend"] if relevant_chunks else "local_vector",
        "files": analysis["files"],
        "static_warnings": analysis["static_warnings"],
        "top_relevant_chunks": [
            {
                "file_path": c["file_path"],
                "symbol_name": c["symbol_name"],
                "symbol_type": c["symbol_type"],
                "lines": f"{c['start_line']}-{c['end_line']}",
                "similarity": c["similarity"],
            }
            for c in relevant_chunks
        ],
    }

    timeline = list(state.get("agent_timeline", []))
    timeline.append(
        {
            "step": len(timeline) + 1,
            "agent": "Code Understanding Agent",
            "role": "AST Parser & pgvector Code Indexer",
            "status": "COMPLETED",
            "duration_ms": duration_ms,
            "timestamp": _now_iso(),
            "summary": (
                f"Parsed {analysis['total_files']} files ({analysis['total_lines']} lines), "
                f"detected {len(analysis['static_warnings'])} static AST warnings, and indexed "
                f"{chunks_indexed} semantic code chunks into vector store."
            ),
            "details": {
                "files_analyzed": [f["file"] for f in analysis["files"]],
                "warnings_found": len(analysis["static_warnings"]),
                "chunks_indexed": chunks_indexed,
            },
        }
    )

    return {
        "repo_name": repo_name,
        "workspace_path": str(workspace_path),
        "file_contents": analysis["file_contents"],
        "code_structure": code_structure,
        "relevant_chunks": relevant_chunks,
        "iteration": 0,
        "test_history": [],
        "agent_timeline": timeline,
    }


def debugging_node(state: SWEAgentState) -> Dict[str, Any]:
    """
    Agent 2: Debugging Agent
    - Inspects error logs, stack traces, AST static warnings, and retrieved code chunks
    - Pinpoints the exact root cause, affected symbols, and line numbers
    """
    t0 = time.perf_counter()
    root_cause = diagnose_root_cause(
        repo_name=state["repo_name"],
        issue_description=state.get("issue_description", ""),
        error_logs=state.get("error_logs", ""),
        code_structure=state["code_structure"],
        relevant_chunks=state.get("relevant_chunks", []),
        file_contents=state.get("file_contents", {}),
        provider=state.get("llm_provider", "mock"),
        api_key=state.get("api_key", ""),
    )
    duration_ms = round((time.perf_counter() - t0) * 1000, 1)

    bugs_cnt = len(root_cause.get("identified_bugs", []))
    timeline = list(state.get("agent_timeline", []))
    timeline.append(
        {
            "step": len(timeline) + 1,
            "agent": "Debugging Agent",
            "role": "Error Log & Root Cause Diagnostician",
            "status": "COMPLETED",
            "duration_ms": duration_ms,
            "timestamp": _now_iso(),
            "summary": f"Diagnosed {bugs_cnt} root cause defect(s) in `{root_cause.get('primary_file')}` (confidence: {int(root_cause.get('confidence', 0.95) * 100)}%): {root_cause.get('summary')}",
            "details": root_cause,
        }
    )

    return {
        "root_cause_analysis": root_cause,
        "agent_timeline": timeline,
    }


def code_generation_node(state: SWEAgentState) -> Dict[str, Any]:
    """
    Agent 3: Code Generation Agent
    - Proposes code fixes for the diagnosed root cause
    - On self-healing retry iterations (iteration > 1), inspects pytest failure output
      and modifies the proposed patch to resolve failing edge cases
    """
    t0 = time.perf_counter()
    next_iteration = state.get("iteration", 0) + 1
    last_failure = state.get("last_test_failure")
    file_contents = state.get("file_contents", {})

    patch_result = generate_code_fix(
        repo_name=state["repo_name"],
        root_cause=state["root_cause_analysis"],
        file_contents=file_contents,
        iteration=next_iteration,
        last_test_failure=last_failure,
        demonstrate_self_healing=state.get("demonstrate_self_healing", True),
        provider=state.get("llm_provider", "mock"),
        api_key=state.get("api_key", ""),
    )

    modified_files: Dict[str, str] = patch_result.get("modified_files", {})
    diffs = []
    for fpath, new_code in modified_files.items():
        old_code = file_contents.get(fpath, "")
        diff_str = compute_unified_diff(old_code, new_code, fpath)
        if diff_str:
            diffs.append(diff_str)

    unified_diff = "\n".join(diffs)
    duration_ms = round((time.perf_counter() - t0) * 1000, 1)

    proposed_changes = {
        "iteration": next_iteration,
        "modified_files": modified_files,
        "unified_diff": unified_diff,
        "explanation": patch_result.get("explanation", ""),
        "iteration_note": patch_result.get("iteration_note", ""),
    }

    timeline = list(state.get("agent_timeline", []))
    action_label = (
        f"Self-Healing Patch Refinement (Iteration {next_iteration})"
        if next_iteration > 1
        else f"Initial Patch Generation (Iteration {next_iteration})"
    )
    timeline.append(
        {
            "step": len(timeline) + 1,
            "agent": "Code Generation Agent",
            "role": action_label,
            "status": "COMPLETED",
            "duration_ms": duration_ms,
            "timestamp": _now_iso(),
            "summary": patch_result.get("iteration_note") or patch_result.get("explanation", "Generated code fix."),
            "details": {
                "iteration": next_iteration,
                "files_modified": list(modified_files.keys()),
                "triggered_by_test_failure": bool(last_failure),
            },
        }
    )

    return {
        "iteration": next_iteration,
        "proposed_changes": proposed_changes,
        "agent_timeline": timeline,
    }


def testing_node(state: SWEAgentState) -> Dict[str, Any]:
    """
    Agent 4: Testing Agent
    - Generates comprehensive pytest unit tests (or reuses generated suite across iterations)
    - Applies candidate code fix + unit tests into the isolated sandbox workspace
    - Executes pytest and inspects pass/fail results
    - If tests fail and iteration < max_iterations, triggers self-healing loop back to Code Generation Agent
    """
    t0 = time.perf_counter()
    iteration = state.get("iteration", 1)
    workspace_path = Path(state["workspace_path"])
    proposed_changes = dict(state.get("proposed_changes", {}))

    # Generate unit tests on iteration 1 (or reuse/update on subsequent iterations)
    generated_tests = state.get("generated_tests")
    if not generated_tests:
        generated_tests = generate_unit_tests(
            repo_name=state["repo_name"],
            root_cause=state["root_cause_analysis"],
            file_contents=state.get("file_contents", {}),
            proposed_changes=proposed_changes,
            provider=state.get("llm_provider", "mock"),
            api_key=state.get("api_key", ""),
        )

    test_file_path = generated_tests["test_file_path"]
    test_code = generated_tests["test_code"]
    proposed_changes["test_file_path"] = test_file_path

    # Write candidate code fix and generated test suite to isolated workspace
    files_to_write = dict(proposed_changes.get("modified_files", {}))
    files_to_write[test_file_path] = test_code
    apply_files_to_workspace(workspace_path, files_to_write)

    # Execute pytest in isolated workspace
    pytest_result = run_pytest_in_workspace(workspace_path)
    duration_ms = round((time.perf_counter() - t0) * 1000, 1)

    passed = pytest_result["passed"]
    max_iterations = state.get("max_iterations", 3)
    will_retry = (not passed) and (iteration < max_iterations)

    note = (
        f"All {pytest_result['passed_count']} unit tests passed!"
        if passed
        else (
            f"Caught {pytest_result['failed_count']} failing test(s) ({', '.join(pytest_result['failing_tests'])}); "
            f"routing failure traceback back to Code Generation Agent for Iteration {iteration + 1}."
            if will_retry
            else f"Tests finished with {pytest_result['failed_count']} failure(s) at max iteration {iteration}."
        )
    )

    iteration_record = {
        "iteration": iteration,
        "passed": passed,
        "passed_count": pytest_result["passed_count"],
        "failed_count": pytest_result["failed_count"],
        "failing_tests": pytest_result["failing_tests"],
        "exit_code": pytest_result["exit_code"],
        "output": pytest_result["output"],
        "patch_note": proposed_changes.get("iteration_note", ""),
        "note": note,
        "duration_ms": duration_ms,
    }

    test_history = list(state.get("test_history", []))
    test_history.append(iteration_record)

    timeline = list(state.get("agent_timeline", []))
    timeline.append(
        {
            "step": len(timeline) + 1,
            "agent": "Testing Agent",
            "role": f"Unit Test Generator & Pytest Runner (Iteration {iteration})",
            "status": "PASSED" if passed else ("SELF_HEAL_RETRY" if will_retry else "FAILED"),
            "duration_ms": duration_ms,
            "timestamp": _now_iso(),
            "summary": note,
            "details": {
                "iteration": iteration,
                "passed": passed,
                "passed_count": pytest_result["passed_count"],
                "failed_count": pytest_result["failed_count"],
                "failing_tests": pytest_result["failing_tests"],
            },
        }
    )

    return {
        "proposed_changes": proposed_changes,
        "generated_tests": generated_tests,
        "test_history": test_history,
        "tests_passed": passed,
        "last_test_failure": None if passed else pytest_result["output"],
        "agent_timeline": timeline,
    }


def code_review_node(state: SWEAgentState) -> Dict[str, Any]:
    """
    Agent 5: Code Review Agent
    - Performs automated code review across correctness, edge cases, security, and test coverage
    - Builds and optionally submits the GitHub Pull Request for human review
    """
    t0 = time.perf_counter()
    review = review_code_changes(
        repo_name=state["repo_name"],
        root_cause=state["root_cause_analysis"],
        proposed_changes=state["proposed_changes"],
        test_history=state.get("test_history", []),
        provider=state.get("llm_provider", "mock"),
        api_key=state.get("api_key", ""),
    )

    pr_payload = build_pull_request_payload(
        run_id=state["run_id"],
        repo_source=state["repo_source"],
        repo_name=state["repo_name"],
        root_cause=state["root_cause_analysis"],
        proposed_changes=state["proposed_changes"],
        test_history=state.get("test_history", []),
        code_review=review,
        github_token=state.get("github_token"),
        create_github_pr=state.get("create_github_pr", False),
    )
    duration_ms = round((time.perf_counter() - t0) * 1000, 1)

    timeline = list(state.get("agent_timeline", []))
    timeline.append(
        {
            "step": len(timeline) + 1,
            "agent": "Code Review Agent",
            "role": "Automated Quality Gate & Pull Request Publisher",
            "status": "COMPLETED",
            "duration_ms": duration_ms,
            "timestamp": _now_iso(),
            "summary": (
                f"Review Verdict: {review.get('verdict')} (Score: {review.get('score')}/100). "
                f"Created Pull Request `{pr_payload.get('title')}` on branch `{pr_payload.get('branch')}`."
            ),
            "details": {
                "verdict": review.get("verdict"),
                "score": review.get("score"),
                "branch": pr_payload.get("branch"),
                "pr_status": pr_payload.get("status"),
            },
        }
    )

    return {
        "code_review": review,
        "pull_request": pr_payload,
        "agent_timeline": timeline,
    }

