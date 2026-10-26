"""Local FastAPI interface: uv run uvicorn src.app:app --host 127.0.0.1."""

import json
from contextlib import aclosing, asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .gateway import (
    AuthenticationError, GatewayConnectionError, GatewayInputError,
    GatewayProviderError, IncompleteStreamError, RateLimitExceededError,
    UnifiedLLMGateway,
)
from .pricing import MODEL_PRICING
from .schemas import Provider

WEB = Path(__file__).parent / "web"


class StreamRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    provider: Provider
    model: str
    prompt: str = Field(min_length=1, max_length=16000)
    temperature: float = Field(default=0.7, ge=0, le=1, allow_inf_nan=False)
    max_tokens: int = Field(default=512, ge=1, le=4096)

    @model_validator(mode="after")
    def check_selection(self) -> "StreamRequest":
        if not self.prompt.strip():
            raise ValueError("Prompt must contain text.")
        if self.model not in MODEL_PRICING or MODEL_PRICING[self.model].provider != self.provider:
            raise ValueError("Provider/model mismatch.")
        return self


def sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=True)}\n\n"


def public_error(exc: GatewayProviderError) -> dict[str, str]:
    # Do not serialize exception objects or their potentially sensitive details.
    messages = {
        AuthenticationError: "Set or correct this provider's API key in your local .env, then restart the server.",
        RateLimitExceededError: "Provider rate or quota limit reached. Check your account and try again later.",
        GatewayConnectionError: "Cannot reach the provider. Check your connection and try again.",
        IncompleteStreamError: "The stream ended without complete usage. Partial text and metrics are not final.",
        GatewayInputError: "Check the prompt, model, temperature and output limit.",
    }
    return {"type": type(exc).__name__ if type(exc) in messages else "GatewayProviderError",
            "message": messages.get(type(exc), "The provider request failed. Check account model access and try again.")}


def create_app(gateway_factory=UnifiedLLMGateway) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        load_dotenv(Path(__file__).parent.parent / ".env", override=False)
        # One gateway on this event loop; lazy SDK clients persist across requests.
        app.state.gateway = gateway_factory()
        try:
            yield
        finally:
            try:
                await app.state.gateway.aclose()
            except GatewayProviderError:
                # Static message only, no SDK traceback or secret-bearing details.
                import logging
                logging.getLogger(__name__).warning("Provider client cleanup failed.")

    app = FastAPI(title="AD331 LLM Gateway", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])

    @app.middleware("http")
    async def local_browser_boundary(request: Request, call_next):
        # No cross-origin API access. Protect the local paid endpoint from
        # browser requests initiated by a different website.
        origin = request.headers.get("origin")
        if request.method == "POST" and origin:
            expected = f"{request.url.scheme}://{request.url.netloc}"
            if origin.rstrip("/") != expected:
                return JSONResponse({"message": "Cross-origin requests are not allowed."}, status_code=403)
        if request.method == "POST" and request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"message": "Cross-site requests are not allowed."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request, _exc):
        # FastAPI's default validation body can echo submitted input.
        return JSONResponse({"message": "Invalid request. Select a supported model, enter 1–16,000 prompt characters, "
                            "use temperature 0–1 and an output limit of 1–4,096."}, status_code=422)

    @app.get("/")
    async def index():
        return FileResponse(WEB / "index.html")

    @app.get("/app.js")
    async def javascript():
        return FileResponse(WEB / "app.js", media_type="text/javascript")

    @app.get("/style.css")
    async def stylesheet():
        return FileResponse(WEB / "style.css", media_type="text/css")

    @app.get("/api/models")
    async def models():
        return [{"id": model, "provider": rate.provider} for model, rate in MODEL_PRICING.items()]

    @app.post("/api/stream")
    async def stream(body: StreamRequest, request: Request):
        async def events():
            try:
                upstream = request.app.state.gateway.stream(
                    body.prompt, body.model, body.temperature, max_tokens=body.max_tokens)
                async with aclosing(upstream):
                    async for chunk in upstream:
                        payload = chunk.model_dump(mode="json")
                        cost = chunk.telemetry.total_cost_usd if chunk.telemetry else None
                        # Format Decimal on the server, preserving exact internal cost.
                        payload["display_cost_usd"] = None if cost is None else f"{cost:.6f}"
                        yield sse("chunk", payload)
            except GatewayProviderError as exc:
                yield sse("error", public_error(exc))
            except Exception:
                yield sse("error", {"type": "GatewayProviderError", "message": "The request failed safely. Please try again."})
            # CancelledError/GeneratorExit propagate; aclosing closes the upstream.
        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    return app


app = create_app()
