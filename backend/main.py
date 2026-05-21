"""FastAPI application entry point."""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import CORS_ORIGINS, OUTPUTS_DIR
from backend.routers import tasks, reports
from backend.events.stream_manager import router as stream_router, broadcast_event, set_main_loop
from backend.services.crew_executor import set_sse_broadcaster


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure the outputs directory exists on startup."""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    # Wire up the SSE broadcaster so crew events reach connected clients
    set_sse_broadcaster(broadcast_event)
    # Register the main event loop so crew threads can enqueue SSE events
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    set_main_loop(loop)
    yield


app = FastAPI(
    title="Research Gap Analysis API",
    description="FastAPI backend for the AI-powered research gap analysis system",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(stream_router, prefix="/api")


@app.get("/api/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
