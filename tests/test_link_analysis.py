import asyncio
import json
from pathlib import Path
from openai import AsyncOpenAI
from unittest.mock import AsyncMock

import httpx
import pytest

from app.main import app
from app.schemas import ModelResult
from app.services import llm_service, website_extractor
from app.utils import validators

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "response.json"
HTML = b"""<title>Northstar Bike Workshop</title><nav><a href='/services'>Services</a></nav>
<main><h1>Bicycle repair</h1><p>Bicycle tune-ups and brake repairs in Pune.</p>
<script>hidden text</script></main>"""


def request(method, path, **kwargs):
    async def send():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def model_result():
    data = json.loads(EXAMPLE.read_text())
    return ModelResult(brand=data["brand"], analysis=data["analysis"])


def test_success_through_extractor_and_provider(monkeypatch):
    async def fetch(url):
        return url, HTML

    calls = []

    def complete(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={
            "id": "resp_test",
            "object": "response",
            "created_at": 0,
            "model": "test-model",
            "status": "completed",
            "output": [{
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{
                    "type": "output_text",
                    "text": model_result().model_dump_json(),
                    "annotations": [],
                }],
            }],
        })

    def provider(**kwargs):
        transport = httpx.MockTransport(complete)
        return AsyncOpenAI(http_client=httpx.AsyncClient(transport=transport), **kwargs)

    monkeypatch.setattr(website_extractor, "fetch", fetch)
    monkeypatch.setattr(llm_service, "model_settings", lambda: ("test-key", "test-model", None))
    monkeypatch.setattr(llm_service, "gemini_settings", lambda: (None, "unused"))
    monkeypatch.setattr(llm_service, "AsyncOpenAI", provider)
    response = request("POST", "/link-analysis", json={"url": "https://example.com/"})
    assert response.status_code == 200
    assert response.json() == json.loads(EXAMPLE.read_text())
    assert calls[0]["text"]["format"]["strict"] is True
    assert "Bicycle tune-ups" in calls[0]["input"]
    assert "hidden text" not in calls[0]["input"]


@pytest.mark.parametrize("url", ["not a URL", "ftp://example.com"])
def test_invalid_url(url):
    response = request("POST", "/link-analysis", json={"url": url})
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/", "http://localhost/", "http://[::1]/",
    "http://169.254.169.254/", "https://user:pass@example.com/", "http://example.com:8080/",
])
def test_unsafe_url(url):
    response = request("POST", "/link-analysis", json={"url": url})
    assert response.status_code == 400
    assert response.json()["error"] == "unsafe_url"


def test_redirect_revalidates_destination(monkeypatch):
    requests = []

    def redirect(request):
        requests.append(request)
        return httpx.Response(302, headers={"location": "http://127.0.0.1/"})

    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        website_extractor.httpx, "AsyncClient",
        lambda **kwargs: original_client(transport=httpx.MockTransport(redirect), **kwargs),
    )

    async def exercise():
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(loop, "getaddrinfo", AsyncMock(
            return_value=[(0, 0, 0, "", ("93.184.216.34", 443))]
        ))
        with pytest.raises(validators.UnsafeURL):
            await website_extractor.fetch(httpx.URL("https://example.com/"))

    asyncio.run(exercise())
    assert len(requests) == 1
    assert requests[0].url.host == "93.184.216.34"
    assert requests[0].headers["host"] == "example.com"
    assert requests[0].extensions["sni_hostname"] == "example.com"


@pytest.mark.parametrize(("exception", "status", "code"), [
    (website_extractor.WebsiteUnavailable("blocked"), 502, "website_unavailable"),
    (llm_service.MissingCredentials("missing"), 503, "provider_unconfigured"),
    (llm_service.ModelUnavailable("provider unavailable"), 502, "analysis_unavailable"),
])
def test_upstream_errors(monkeypatch, exception, status, code):
    monkeypatch.setattr("app.main.analyze_website", AsyncMock(side_effect=exception))
    response = request("POST", "/link-analysis", json={"url": "https://example.com/"})
    assert response.status_code == status
    assert response.json()["error"] == code


def test_rejects_ungrounded_service_quote():
    with pytest.raises(llm_service.ModelUnavailable, match="matching website evidence"):
        llm_service.validate_result(model_result(), {"page_1": "Unrelated information"})


def test_large_page_uses_bounded_html_prefix(monkeypatch):
    html = b"<main><p>Northstar Bike Workshop offers bicycle tune-ups and brake repair.</p></main>"
    cap = len(html) + 16

    class LargePage(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield html
            yield b" " * cap
            pytest.fail("The extractor kept reading after the byte limit")

    def respond(request):
        return httpx.Response(
            200, headers={"content-type": "text/html"}, stream=LargePage()
        )

    original_client = httpx.AsyncClient
    monkeypatch.setattr(website_extractor, "MAX_BYTES", cap)
    monkeypatch.setattr(website_extractor, "resolve_public", AsyncMock(return_value=["93.184.216.34"]))
    monkeypatch.setattr(
        website_extractor.httpx, "AsyncClient",
        lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs),
    )

    pages = asyncio.run(website_extractor.extract_website("https://example.com/"))
    assert len(pages) == 1
    assert "bicycle tune-ups and brake repair" in pages[0].text


def test_application_serves_form_and_assets():
    page = request("GET", "/")
    assert page.status_code == 200
    assert 'id="website-url"' in page.text
    assert request("GET", "/assets/analysis.js").status_code == 200
    assert request("GET", "/assets/analysis.css").status_code == 200


def test_docs():
    assert request("GET", "/docs").status_code == 200
    assert "/link-analysis" in request("GET", "/openapi.json").json()["paths"]



@pytest.mark.parametrize("first_status", [None, 503, 429])
def test_gemini_analysis_through_api(monkeypatch, first_status):
    calls = 0
    async def fetch(url):
        return url, HTML

    def generate(request):
        nonlocal calls
        calls += 1
        if calls == 1 and first_status:
            return httpx.Response(first_status)
        assert request.url.host == "generativelanguage.googleapis.com"
        assert request.url.path.endswith("/gemini-3.1-flash-lite:streamGenerateContent")
        assert request.headers["x-goog-api-key"] == "test-gemini-key"
        body = json.loads(request.content)
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        assert "Bicycle tune-ups" in body["contents"][0]["parts"][0]["text"]
        assert request.url.params["alt"] == "sse"
        text = model_result().model_dump_json()
        chunks = [
            {"content": {"parts": [{"text": text[:100]}]}},
            {"content": {"parts": [{"text": text[100:]}]}, "finishReason": "STOP"},
        ]
        events = "".join(f"data: {json.dumps({'candidates': [part]})}\n\n" for part in chunks)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=events)

    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setattr(website_extractor, "fetch", fetch)
    monkeypatch.setattr(llm_service, "AsyncClient", lambda **kwargs: httpx.AsyncClient(
        transport=httpx.MockTransport(generate), **kwargs
    ))

    response = request("POST", "/link-analysis", json={"url": "https://example.com/"})
    if first_status == 429:
        assert calls == 1
        assert response.status_code == 502
        assert "quota" in response.json()["detail"]
        return
    assert calls == (2 if first_status == 503 else 1)
    assert response.status_code == 200
    assert response.json() == json.loads(EXAMPLE.read_text())
