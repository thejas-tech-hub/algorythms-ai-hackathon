"""
Uvicorn entrypoint for the AI Interview Agent.

Usage:
    uvicorn main:app --reload
    python main.py
"""

import uvicorn

from app.main import app  # noqa: F401 — re-exported for uvicorn discovery

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
