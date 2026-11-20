from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.schemas import ErrorResponse, LinkRequest, LinkResponse
from app.services.analysis_service import analyze_website
from app.services.llm_service import MissingCredentials, ModelUnavailable
from app.services.website_extractor import WebsiteUnavailable
from app.utils.validators import UnsafeURL

app = FastAPI(title="Website Link Analysis API", version="1.0.0")
web_directory = Path(__file__).with_name("web")
app.mount("/assets", StaticFiles(directory=web_directory), name="assets")


@app.get("/", include_in_schema=False)
async def application_page() -> FileResponse:
    return FileResponse(web_directory / "index.html")


def error(status: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status, content=ErrorResponse(error=code, detail=detail).model_dump()
    )


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
    return error(422, "invalid_request", "Send a JSON object with a valid HTTP or HTTPS url.")


@app.post(
    "/link-analysis",
    response_model=LinkResponse,
    responses={status: {"model": ErrorResponse} for status in (400, 422, 502, 503)},
)
async def link_analysis(request: LinkRequest) -> LinkResponse | JSONResponse:
    try:
        return await analyze_website(str(request.url))
    except UnsafeURL as exc:
        return error(400, "unsafe_url", str(exc))
    except WebsiteUnavailable as exc:
        return error(502, "website_unavailable", str(exc))
    except MissingCredentials as exc:
        return error(503, "provider_unconfigured", str(exc))
    except ModelUnavailable as exc:
        return error(502, "analysis_unavailable", str(exc))
