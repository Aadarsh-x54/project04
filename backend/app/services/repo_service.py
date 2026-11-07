import ast
import difflib
import os
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Tuple

from app.config import SAMPLE_REPOS_DIR, WORKSPACES_DIR

IGNORED_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
}
CODE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx"}


def _remove_readonly(func, path, _excinfo):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def prepare_workspace(
    run_id: str,
    repo_source: str,
    custom_files: Dict[str, str] | None = None,
) -> Tuple[Path, str]:
    """
    Prepare an isolated workspace directory for `run_id` from:
    - custom inline files (`custom_files` dict)
    - sample:<name> (built-in sample repo)
    - local filesystem path
    - GitHub URL (https://github.com/owner/repo)
    Returns (workspace_path, repo_name).
    """
    workspace_path = WORKSPACES_DIR / run_id
    if workspace_path.exists():
        shutil.rmtree(workspace_path, onerror=_remove_readonly)

    source = repo_source.strip()
    if custom_files:
        workspace_path.mkdir(parents=True, exist_ok=True)
        for rel_path, content in custom_files.items():
            target = (workspace_path / rel_path).resolve()
            if str(target).startswith(str(workspace_path.resolve())):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
        repo_name = source.replace("sample:", "").replace("custom:", "") or "custom_sandbox"
        return workspace_path, repo_name

    if source.startswith("sample:"):
        sample_name = source.split("sample:", 1)[1].strip()
        src_dir = SAMPLE_REPOS_DIR / sample_name
        if not src_dir.exists():
            raise ValueError(f"Sample repository '{sample_name}' not found in {SAMPLE_REPOS_DIR}")
        shutil.copytree(src_dir, workspace_path)
        return workspace_path, sample_name

    if source.startswith("http://") or source.startswith("https://") or source.startswith("git@"):
        repo_name = source.rstrip("/").split("/")[-1].replace(".git", "")
        result = subprocess.run(
            ["git", "clone", "--depth", "1", source, str(workspace_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to clone GitHub repository '{source}': {result.stderr.strip()}")
        return workspace_path, repo_name

    # Local path
    local_dir = Path(source)
    if not local_dir.is_absolute():
        candidate = SAMPLE_REPOS_DIR / source
        if candidate.exists():
            local_dir = candidate
    if not local_dir.exists() or not local_dir.is_dir():
        raise ValueError(f"Repository path '{source}' does not exist or is not a directory.")

    shutil.copytree(
        local_dir,
        workspace_path,
        ignore=shutil.ignore_patterns(*IGNORED_DIRS),
    )
    return workspace_path, local_dir.name


def analyze_python_ast(file_path: Path, rel_path: str, source_text: str) -> Dict[str, Any]:
    """Parse Python AST to extract classes, functions, imports, static smells, and semantic code chunks."""
    lines = source_text.splitlines()
    classes: List[Dict[str, Any]] = []
    functions: List[Dict[str, Any]] = []
    imports: List[str] = []
    static_warnings: List[Dict[str, Any]] = []
    chunks: List[Dict[str, Any]] = []

    try:
        tree = ast.parse(source_text, filename=rel_path)
    except SyntaxError as exc:
        static_warnings.append(
            {
                "file": rel_path,
                "line": exc.lineno or 1,
                "severity": "HIGH",
                "category": "SyntaxError",
                "message": f"SyntaxError: {exc.msg}",
            }
        )
        return {
            "file": rel_path,
            "language": "python",
            "line_count": len(lines),
            "classes": [],
            "functions": [],
            "imports": [],
            "static_warnings": static_warnings,
            "chunks": [
                {
                    "file_path": rel_path,
                    "symbol_name": Path(rel_path).stem,
                    "symbol_type": "module",
                    "start_line": 1,
                    "end_line": len(lines),
                    "content": source_text,
                }
            ],
        }

    # Walk top-level and nested nodes for imports, classes, functions, and static bug patterns
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                imports.append(f"{mod}.{alias.name}" if mod else alias.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Check for mutable default arguments (e.g. def __init__(..., tags=[]))
            for default in node.args.defaults + node.args.kw_defaults:
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    static_warnings.append(
                        {
                            "file": rel_path,
                            "line": node.lineno,
                            "severity": "HIGH",
                            "category": "MutableDefaultArgument",
                            "message": f"Function '{node.name}' uses a mutable default argument (list/dict/set) which persists across calls.",
                        }
                    )
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            # Check division operations for potential ZeroDivisionError or suspicious divisor
            divisor_src = ast.get_source_segment(source_text, node.right) or ""
            line_no = getattr(node, "lineno", 1)
            if divisor_src and not divisor_src.replace(".", "", 1).isdigit():
                static_warnings.append(
                    {
                        "file": rel_path,
                        "line": line_no,
                        "severity": "MEDIUM",
                        "category": "PotentialZeroDivision",
                        "message": f"Division by variable '{divisor_src}' at line {line_no}; verify zero-guard handling.",
                    }
                )
            elif divisor_src == "10.0" or divisor_src == "10":
                static_warnings.append(
                    {
                        "file": rel_path,
                        "line": line_no,
                        "severity": "HIGH",
                        "category": "SuspiciousPercentageDivisor",
                        "message": f"Division by {divisor_src} at line {line_no} in percentage calculation (expected 100.0).",
                    }
                )

    for item in tree.body:
        if isinstance(item, ast.ClassDef):
            end_lineno = getattr(item, "end_lineno", item.lineno)
            method_names = []
            for sub in item.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_names.append(sub.name)
                    sub_end = getattr(sub, "end_lineno", sub.lineno)
                    sub_code = "\n".join(lines[sub.lineno - 1 : sub_end])
                    functions.append(
                        {
                            "name": f"{item.name}.{sub.name}",
                            "args": [a.arg for a in sub.args.args],
                            "start_line": sub.lineno,
                            "end_line": sub_end,
                            "docstring": ast.get_docstring(sub) or "",
                        }
                    )
                    chunks.append(
                        {
                            "file_path": rel_path,
                            "symbol_name": f"{item.name}.{sub.name}",
                            "symbol_type": "method",
                            "start_line": sub.lineno,
                            "end_line": sub_end,
                            "content": sub_code,
                        }
                    )
            class_code = "\n".join(lines[item.lineno - 1 : end_lineno])
            classes.append(
                {
                    "name": item.name,
                    "methods": method_names,
                    "start_line": item.lineno,
                    "end_line": end_lineno,
                    "docstring": ast.get_docstring(item) or "",
                }
            )
            chunks.append(
                {
                    "file_path": rel_path,
                    "symbol_name": item.name,
                    "symbol_type": "class",
                    "start_line": item.lineno,
                    "end_line": end_lineno,
                    "content": class_code,
                }
            )
        elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end_lineno = getattr(item, "end_lineno", item.lineno)
            fn_code = "\n".join(lines[item.lineno - 1 : end_lineno])
            functions.append(
                {
                    "name": item.name,
                    "args": [a.arg for a in item.args.args],
                    "start_line": item.lineno,
                    "end_line": end_lineno,
                    "docstring": ast.get_docstring(item) or "",
                }
            )
            chunks.append(
                {
                    "file_path": rel_path,
                    "symbol_name": item.name,
                    "symbol_type": "function",
                    "start_line": item.lineno,
                    "end_line": end_lineno,
                    "content": fn_code,
                }
            )

    if not chunks:
        chunks.append(
            {
                "file_path": rel_path,
                "symbol_name": Path(rel_path).stem,
                "symbol_type": "module",
                "start_line": 1,
                "end_line": len(lines),
                "content": source_text,
            }
        )

    return {
        "file": rel_path,
        "language": "python",
        "line_count": len(lines),
        "classes": classes,
        "functions": functions,
        "imports": sorted(set(imports)),
        "static_warnings": static_warnings,
        "chunks": chunks,
    }


def analyze_repository(workspace_path: Path) -> Dict[str, Any]:
    """
    Scan workspace files, build AST structure map, collect static warnings,
    and extract semantic chunks for vector indexing.
    """
    file_summaries: List[Dict[str, Any]] = []
    all_warnings: List[Dict[str, Any]] = []
    all_chunks: List[Dict[str, Any]] = []
    file_contents: Dict[str, str] = {}
    total_lines = 0

    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for fname in sorted(files):
            fpath = Path(root) / fname
            if fpath.suffix.lower() not in CODE_EXTENSIONS:
                continue
            rel_path = fpath.relative_to(workspace_path).as_posix()
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            file_contents[rel_path] = content
            if fpath.suffix.lower() == ".py":
                analysis = analyze_python_ast(fpath, rel_path, content)
                total_lines += analysis["line_count"]
                all_warnings.extend(analysis["static_warnings"])
                all_chunks.extend(analysis["chunks"])
                file_summaries.append(
                    {
                        "file": rel_path,
                        "language": analysis["language"],
                        "line_count": analysis["line_count"],
                        "classes": analysis["classes"],
                        "functions": analysis["functions"],
                        "imports": analysis["imports"],
                        "warning_count": len(analysis["static_warnings"]),
                    }
                )
            else:
                lines = content.splitlines()
                total_lines += len(lines)
                all_chunks.append(
                    {
                        "file_path": rel_path,
                        "symbol_name": Path(rel_path).stem,
                        "symbol_type": "module",
                        "start_line": 1,
                        "end_line": len(lines),
                        "content": content,
                    }
                )
                file_summaries.append(
                    {
                        "file": rel_path,
                        "language": fpath.suffix.lstrip("."),
                        "line_count": len(lines),
                        "classes": [],
                        "functions": [],
                        "imports": [],
                        "warning_count": 0,
                    }
                )

    return {
        "total_files": len(file_summaries),
        "total_lines": total_lines,
        "files": file_summaries,
        "static_warnings": all_warnings,
        "chunks": all_chunks,
        "file_contents": file_contents,
    }


def compute_unified_diff(original_code: str, modified_code: str, file_path: str) -> str:
    """Create a standard unified diff between original and modified source strings."""
    orig_lines = original_code.splitlines(keepends=True)
    mod_lines = modified_code.splitlines(keepends=True)
    diff = difflib.unified_diff(
        orig_lines,
        mod_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        lineterm="\n",
    )
    return "".join(diff)

