"""
Command-Line Interface (CLI) for the AI Software Engineering Agent.
Allows running the 5-agent LangGraph pipeline directly from the terminal.

Usage:
    python cli.py --repo sample:ecommerce_checkout_bug
    python cli.py --repo sample:async_task_queue_bug
    python cli.py --repo sample:graph_shortest_path_bug
"""

import argparse
import sys

from app.database import init_db_engine, Base, get_session_local
from app.main import execute_agent_run
from app.schemas import RunAgentRequest


def main():
    parser = argparse.ArgumentParser(description="AI Software Engineering Agent CLI")
    parser.add_argument(
        "--repo",
        default="sample:ecommerce_checkout_bug",
        help="GitHub URL, local path, or sample ID (sample:ecommerce_checkout_bug, sample:async_task_queue_bug, sample:graph_shortest_path_bug)",
    )
    parser.add_argument("--issue", default="", help="Issue description")
    parser.add_argument("--logs", default="", help="Error logs or stack trace")
    parser.add_argument("--provider", default="auto", help="LLM provider: auto | gemini | openai | mock")
    parser.add_argument("--max-iterations", type=int, default=3, help="Max self-healing test iterations")
    parser.add_argument(
        "--no-self-heal-demo",
        action="store_true",
        help="Disable multi-step self-healing demonstration",
    )
    args = parser.parse_args()

    engine = init_db_engine()
    Base.metadata.create_all(bind=engine)
    SessionLocal = get_session_local()
    db = SessionLocal()

    print("=" * 78)
    print(f" Launching 5-Agent LangGraph Pipeline on: {args.repo}")
    print("=" * 78)

    try:
        req = RunAgentRequest(
            repo_source=args.repo,
            issue_description=args.issue,
            error_logs=args.logs,
            llm_provider=args.provider,
            max_iterations=args.max_iterations,
            demonstrate_self_healing=not args.no_self_heal_demo,
        )
        run = execute_agent_run(req, db=db)

        for step in run.agent_timeline or []:
            print(f"\n[Step {step['step']}] {step['agent']} ({step['role']}) — {step['status']} ({step['duration_ms']} ms)")
            print(f"  -> {step['summary']}")

        print("\n" + "-" * 78)
        print(f"SELF-HEALING TEST HISTORY ({run.iterations_used} Iteration(s)):")
        for it in run.test_history or []:
            badge = "PASSED" if it["passed"] else "FAILED -> SELF-HEAL RETRY"
            print(f"  * Iteration #{it['iteration']} [{badge}]: {it['passed_count']} passed, {it['failed_count']} failed")
            print(f"    Note: {it['note']}")

        print("\n" + "-" * 78)
        print("UNIFIED DIFF:")
        print(run.proposed_changes.get("unified_diff", ""))

        print("-" * 78)
        print(f"CODE REVIEW VERDICT: {run.code_review.get('verdict')} (Score: {run.code_review.get('score')}/100)")
        print(f"PULL REQUEST: {run.pull_request.get('title')}")
        print(f"BRANCH:       {run.pull_request.get('branch')} -> {run.pull_request.get('base_branch')}")
        print("=" * 78)
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

