from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_settings
from app.database import close_db, ensure_indexes
from app.routers import auth, chat, files


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await ensure_indexes()
    except Exception:
        pass
    yield
    await close_db()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        lifespan=lifespan,
    )

    origins = settings.cors_origin_list or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/api")
    app.include_router(files.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")

    @app.get("/health", tags=["health"])
    async def health() -> dict:
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
