#!/usr/bin/env python3
"""
Entry point for running the User Module application.
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8009,
        reload=True,
        reload_dirs=["app", "templates"]
    )
