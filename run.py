"""Single command launcher for LedgerLens."""
import os
import sys
import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("⚡ Starting LedgerLens — Autonomous AP & Invoice Copilot")
    print("=" * 60)
    print("Access the Web UI at: http://localhost:8000")
    print("Press Ctrl+C to stop the server.\n")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
