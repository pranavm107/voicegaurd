import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["api", "ml", "bot", "reports", "dashboard"],
        reload_excludes=["venv/*", "*.pyc", "__pycache__/*", "test_audio/*", "model_cache/*"]
    )
