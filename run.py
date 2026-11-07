"""
Unified Full-Stack Launcher for AI Software Engineering Agent.
Starts both the Frontend UI and FastAPI + LangGraph Backend on http://localhost:8000
"""

import sys
from pathlib import Path
import uvicorn

BACKEND_DIR = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

if __name__ == "__main__":
    print("Starting Unified AI Software Engineering Agent (Frontend + Backend) on http://localhost:8000 ...")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True, reload_dirs=[str(BACKEND_DIR)])

