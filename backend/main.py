from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from backend.config import settings

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("=== SERVER STARTUP INITIATED ===")
    logger.info("Narrative Engine Starting up...")
    yield
    # Shutdown
    print("=== SERVER SHUTDOWN INITIATED ===")
    logger.info("Narrative Engine Shutting down...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Neuro-Symbolic Narrative Engine powered by Gemini",
    lifespan=lifespan
)

logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development convenience
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.routes import narrative

app.include_router(narrative.router, prefix=f"{settings.API_PREFIX}/narrative", tags=["Narrative"])

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.VERSION, "model": settings.GEMINI_MODEL}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
