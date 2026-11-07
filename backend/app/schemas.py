from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class RunAgentRequest(BaseModel):
    repo_source: str = Field(
        default="sample:ecommerce_checkout_bug",
        description="GitHub URL, local directory path, or built-in sample ID (sample:ecommerce_checkout_bug, sample:async_task_queue_bug)",
    )
    issue_description: Optional[str] = Field(
        default="",
        description="Description of the bug or unexpected behavior",
    )
    error_logs: Optional[str] = Field(
        default="",
        description="Stack trace, exception output, or failing test logs",
    )
    llm_provider: str = Field(
        default="auto",
        description="LLM provider: auto | gemini | openai | mock",
    )
    api_key: Optional[str] = Field(
        default=None,
        description="Optional runtime Gemini or OpenAI API key",
    )
    github_token: Optional[str] = Field(
        default=None,
        description="Optional GitHub Personal Access Token for creating a real PR",
    )
    create_github_pr: bool = Field(
        default=False,
        description="Whether to attempt pushing a branch and opening a GitHub PR if repo is on GitHub",
    )
    max_iterations: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum self-healing test-fix-retest iterations",
    )
    demonstrate_self_healing: bool = Field(
        default=True,
        description="Demonstrate multi-iteration self-healing where Iteration 1 leaves an edge case that Testing Agent catches and Iteration 2 resolves",
    )
    custom_files: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional inline source files {filename: code} for live sandbox debugging",
    )


class VectorSearchRequest(BaseModel):
    run_id: Optional[str] = None
    query: str
    top_k: int = 5


class AgentRunResponse(BaseModel):
    id: str
    repo_source: str
    repo_name: str
    issue_description: Optional[str] = None
    error_logs: Optional[str] = None
    status: str
    llm_provider_used: str
    max_iterations: int
    iterations_used: int
    tests_passed: bool
    code_structure: Optional[Dict[str, Any]] = None
    root_cause_analysis: Optional[Dict[str, Any]] = None
    proposed_changes: Optional[Dict[str, Any]] = None
    generated_tests: Optional[Dict[str, Any]] = None
    test_history: Optional[List[Dict[str, Any]]] = None
    code_review: Optional[Dict[str, Any]] = None
    pull_request: Optional[Dict[str, Any]] = None
    agent_timeline: Optional[List[Dict[str, Any]]] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

