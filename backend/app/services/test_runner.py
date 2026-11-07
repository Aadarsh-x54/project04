import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, List


SUMMARY_PASSED_RE = re.compile(r"(\d+)\s+passed")
SUMMARY_FAILED_RE = re.compile(r"(\d+)\s+failed")
SUMMARY_ERROR_RE = re.compile(r"(\d+)\s+error")


def apply_files_to_workspace(workspace_path: Path, files: Dict[str, str]) -> None:
    """Write modified source or test files into the isolated workspace."""
    for rel_path, content in files.items():
        target = (workspace_path / rel_path).resolve()
        if not str(target).startswith(str(workspace_path.resolve())):
            raise ValueError(f"Unsafe relative path: {rel_path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def run_pytest_in_workspace(workspace_path: Path, timeout_sec: int = 30) -> Dict[str, Any]:
    """
    Execute pytest inside `workspace_path` and parse structured results.
    Returns passed/failed counts, exit code, stdout/stderr, and failure summaries.
    """
    cmd = [sys.executable, "-m", "pytest", "-v", "--tb=short"]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(workspace_path),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        exit_code = proc.returncode
    except subprocess.TimeoutExpired:
        output = f"Pytest execution timed out after {timeout_sec} seconds."
        exit_code = 124

    passed_match = SUMMARY_PASSED_RE.search(output)
    failed_match = SUMMARY_FAILED_RE.search(output)
    error_match = SUMMARY_ERROR_RE.search(output)

    passed_count = int(passed_match.group(1)) if passed_match else 0
    failed_count = int(failed_match.group(1)) if failed_match else 0
    error_count = int(error_match.group(1)) if error_match else 0

    failing_tests: List[str] = []
    for line in output.splitlines():
        if line.startswith("FAILED ") or line.startswith("ERROR "):
            failing_tests.append(line.strip())

    return {
        "passed": exit_code == 0 and failed_count == 0 and error_count == 0,
        "exit_code": exit_code,
        "passed_count": passed_count,
        "failed_count": failed_count + error_count,
        "failing_tests": failing_tests,
        "output": output.strip(),
    }

