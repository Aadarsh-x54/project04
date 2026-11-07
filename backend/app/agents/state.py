from typing import TypedDict, Dict, Any, List, Optional


class SWEAgentState(TypedDict, total=False):
    run_id: str
    repo_source: str
    repo_name: str
    workspace_path: str
    issue_description: str
    error_logs: str

    # Configuration
    llm_provider: str
    api_key: str
    github_token: str
    create_github_pr: bool
    max_iterations: int
    demonstrate_self_healing: bool
    custom_files: Optional[Dict[str, str]]

    # Iterative self-healing state
    iteration: int
    tests_passed: bool
    last_test_failure: Optional[str]

    # Agent outputs
    file_contents: Dict[str, str]
    code_structure: Dict[str, Any]
    relevant_chunks: List[Dict[str, Any]]
    root_cause_analysis: Dict[str, Any]
    proposed_changes: Dict[str, Any]
    generated_tests: Dict[str, Any]
    test_history: List[Dict[str, Any]]
    code_review: Dict[str, Any]
    pull_request: Dict[str, Any]
    agent_timeline: List[Dict[str, Any]]

