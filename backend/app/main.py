import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api import router
from app.core.config import is_development, settings, validate_production_secrets

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
validate_production_secrets()

app = FastAPI(
    title="Restaurant POS & Operations Intelligence API",
    version="0.1.0",
    description="Multi-tenant POS and operations APIs. Camera observations remain unvalidated until tested with restaurant footage.",
    docs_url="/docs" if is_development() else None,
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-Integration-Key"],
)
app.include_router(router)


@app.middleware("http")
async def request_context(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(IntegrityError)
async def duplicate_error(request: Request, exc: IntegrityError):
    return JSONResponse(status_code=409, content={"detail": "That already exists (duplicate name, code or number)."})


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    logging.getLogger(__name__).exception("Unhandled API exception", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
