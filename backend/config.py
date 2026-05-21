"""Application configuration — loads .env and exposes settings."""
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = (BASE_DIR / "outputs").resolve()

load_dotenv(BASE_DIR.parent / ".env")

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
