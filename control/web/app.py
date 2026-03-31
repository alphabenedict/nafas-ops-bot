"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from control.web.routers.auth_router import router as auth_router
from control.web.routers.bots_router import router as bots_router
from control.web.routers.contacts_router import router as contacts_router
from control.web.routers.dashboard_router import router as dashboard_router
from control.web.routers.knowledge_router import router as knowledge_router


def create_app() -> FastAPI:
    app = FastAPI(title="NafasOps Platform", docs_url=None, redoc_url=None)

    @app.get("/health", include_in_schema=False)
    async def health_check():
        return JSONResponse({"status": "ok"})

    app.mount("/static", StaticFiles(directory="static"), name="static")

    app.include_router(auth_router)
    app.include_router(dashboard_router)
    app.include_router(bots_router)
    app.include_router(contacts_router)
    app.include_router(knowledge_router)

    return app
