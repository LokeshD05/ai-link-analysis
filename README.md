# Website Link Analysis

Enter a public website URL to generate a report about its brand, competitors, target search queries, SEO, services, and audience. The FastAPI app serves a web form and a JSON endpoint. The report can be downloaded as JSON from the web interface.

## Run locally

Use Python 3.11 or later. Create a virtual environment, install the dependencies, and copy .env.example to .env if you do not already have one.

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

### macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
test -f .env || cp .env.example .env
```

Set `GEMINI_API_KEY` in the local .env file to use Gemini. The default model is `gemini-3.1-flash-lite`. If `GEMINI_API_KEY` is empty, the app uses `OPENAI_API_KEY` with `gpt-5.4-mini` by default. You can set `GEMINI_MODEL`, `OPENAI_MODEL`, or `OPENAI_FALLBACK_MODEL` in .env to override those settings. Git ignores the local .env file. [Google AI Studio API keys](https://aistudio.google.com/apikey)

Start Uvicorn from the project folder. On Windows, use `.\.venv\Scripts\python.exe` in place of `python`.

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 4001
```

Open the [website analysis app](http://127.0.0.1:4001/), enter a URL, and click **Analyze website**. You can submit another URL from the same page. API documentation is available in [Swagger](http://127.0.0.1:4001/docs).

## API example

`POST /link-analysis` accepts a JSON body with a website URL.

```bash
curl -X POST http://127.0.0.1:4001/link-analysis \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.iana.org/"}'
```

On PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:4001/link-analysis -Method Post -ContentType 'application/json' -Body '{"url":"https://www.iana.org/"}' | ConvertTo-Json -Depth 12
```

The response includes brand details, source URLs, and the five analysis sections. Competitor suggestions are AI-generated. Website-sourced services include checked excerpts, and inferred services are labeled. See the [sample JSON response](examples/response.json).

| Status | Meaning |
| --- | --- |
| 200 | Analysis generated |
| 400 | Unsafe or unsupported website URL |
| 422 | Invalid request body or URL |
| 502 | Website or model provider could not produce a usable result |
| 503 | Model provider credentials missing |

## How it works

The app fetches the submitted page and up to two relevant same-origin pages. It reads up to 4 MB of HTML per page and can analyze readable content from the beginning of larger pages. It extracts metadata and readable text, then sends bounded excerpts to the configured model. It validates the response schema, search-platform coverage, and quoted service evidence. The fetcher checks redirects and destination addresses and blocks private-network access. Sites that require sign-in, JavaScript rendering, or browser interaction may return limited data or a readable error.

## LLM comparison

Standard text pricing in USD per million tokens, checked against provider documentation on 20 November 2026. Cost estimates assume 5,000 input tokens (including schema and instructions) and 1,800 output tokens. Actual usage depends on page text and tokenization.

| Provider and model | Input / output | Context | Structured JSON | Expected speed and suitability | Estimated cost |
| --- | --- | --- | --- | --- | --- |
| OpenAI GPT-5.4 mini | $0.75 / $4.50 | 400K | Strict Responses API schema | Designed for efficient high-volume use. Supports schema-constrained multi-section reports. | $0.01185 |
| Google Gemini 3.1 Flash-Lite | $0.25 / $1.50 | 1,048,576 input tokens | JSON Schema subset | Designed for low latency and simple processing. Lower-cost option implemented in this app. | $0.00395 |
| Anthropic Claude Haiku 5.5 | $0.10 / $0.50 for prompts up to 100K | 1M | Structured outputs | Designed for latency-sensitive extraction. Lowest estimated cost in this comparison and a candidate for a cross-provider evaluation. | $0.00140 |

Provider documentation includes [OpenAI GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini), [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing), [Gemini model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite), [Gemini structured outputs](https://ai.google.dev/gemini-api/docs/structured-output), [Claude Haiku 5.5](https://platform.claude.com/docs/en/models/haiku-5-5/overview), [Claude structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).

**Recommendation.** Use Gemini 3.1 Flash-Lite for local development and demos. It is the lower-cost model among the two providers integrated into the app. Choose GPT-5.4 mini when you want to use OpenAI's strict Responses API schema, with GPT-5.4 available as an optional fallback. Claude Haiku 5.5 is included for comparison. The cost figures are estimates, and the project has no comparative accuracy or latency benchmarks.

## Tests

Run `python -m pytest -q` from the virtual environment. The automated tests use fixtures and mocked model responses and run without API keys. The [verification log](examples/verification.log) includes automated and live checks.

## Deploy to Render

Create a **Web Service** connected to this GitHub repository. Choose the `main` branch and Python 3, then leave **Root Directory** blank. Enter these settings in the Render dashboard. [Render FastAPI deployment guide](https://render.com/docs/deploy-fastapi)

| Setting | Value |
| --- | --- |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT --limit-concurrency 12` |
| Health Check Path | `/openapi.json` |

Under **Environment Variables**, set `GEMINI_API_KEY` for Gemini or `OPENAI_API_KEY` for OpenAI. Store the key in Render and keep it out of GitHub. Render supplies `$PORT` when the service starts. [Render environment variables](https://render.com/docs/configure-environment-variables) and [port binding](https://render.com/docs/web-services#port-binding)

After the deploy succeeds, open the service's `onrender.com` URL and submit a public website to check the full analysis flow. Append `/docs` to open Swagger.
