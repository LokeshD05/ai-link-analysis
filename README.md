# Website Link Analysis API

A FastAPI service that reads a public website and uses Gemini or OpenAI to produce a brand and competitor comparison, five search queries, SEO recommendations, up to five services, and target audience insights.

## Run locally

Use Python 3.11 or later. On Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Set GEMINI_API_KEY in .env using your own API key.
.\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 4000
```

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# Set GEMINI_API_KEY in .env using your own API key.
python -m uvicorn app.main:app --host 0.0.0.0 --port 4000
```

Open the [website analysis application](http://localhost:4000/), enter a public website URL, and select **Analyze website**. The page displays the analysis and lets you download the structured JSON. Swagger is available at [localhost:4000/docs](http://localhost:4000/docs). If you started Uvicorn on port 4001, open [localhost:4001](http://localhost:4001/) instead. Put a [Google AI Studio key](https://aistudio.google.com/apikey) in GEMINI_API_KEY in the local ignored .env file. The default Gemini model is gemini-3.1-flash-lite. If GEMINI_API_KEY is empty, the app uses OPENAI_API_KEY instead. OPENAI_MODEL defaults to gpt-5.4-mini. Set OPENAI_FALLBACK_MODEL=gpt-5.4 to enable one additional attempt on compatible provider or validation failures.

## Request and response

```bash
curl -X POST http://localhost:4000/link-analysis \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.iana.org/"}'
```

In PowerShell:

```powershell
Invoke-RestMethod http://localhost:4000/link-analysis -Method Post -ContentType 'application/json' -Body '{"url":"https://www.iana.org/"}' | ConvertTo-Json -Depth 12
```

See the [complete example response](examples/response.json) for the fictional workshop used in the automated test. The response includes a map from each page ID to its source URL. Service entries with basis "website" include a checked excerpt. Where the site lists fewer than five services, the response can include fewer entries or clearly labeled inferred recommendations.

Competitor names and comparisons are AI-generated suggestions, with potential strengths and gaps presented as hypotheses. The number of suggestions depends on available evidence. The five search queries collectively cover Google, Facebook, Instagram, LinkedIn, and X. The response contains no search volume or ranking fields.

| HTTP status | Response |
| --- | --- |
| 200 | Brand, sources and all five analysis sections |
| 400 | Unsafe URL, unsupported port or nonpublic destination |
| 422 | Invalid input |
| 502 | Website inaccessible, insufficient readable HTML, or provider failed to return a valid analysis |
| 503 | Provider credentials missing |

Example error:

```json
{"success":false,"error":"unsafe_url","detail":"The URL must resolve to public addresses."}
```

## Extraction and validation

The service reads the submitted page and up to two relevant same-origin links. It extracts metadata and readable text, strips common navigation and script content, deduplicates text, and sends at most 18,000 extracted characters in one schema-constrained model call. It validates redirects and DNS results, connects directly to a validated public IP, and preserves the original HTTP Host and TLS hostname. Fetches have time, size, and redirect limits.

Extraction works with server-rendered HTML. JavaScript-only pages, login walls, bot protections, and sites requiring unsupported content encoding can return partial evidence or an error. Model output is probabilistic. The service validates structure, platform coverage and quoted excerpts, while SEO, audience and competitor judgments remain recommendations.

## LLM comparison

Standard text pricing in USD per million tokens, checked against provider documentation on 20 November 2026. Cost estimates assume 5,000 input tokens (including schema and instructions) and 1,800 output tokens. Actual usage depends on page text and tokenization.

| Provider and model | Input / output | Context | Structured JSON | Expected speed and suitability | Estimated cost |
| --- | --- | --- | --- | --- | --- |
| OpenAI GPT-5.4 mini | $0.75 / $4.50 | 400K | Strict Responses API schema | Designed for efficient high-volume use. Default for multi-section synthesis and schema validation. | $0.01185 |
| Google Gemini 3.1 Flash-Lite | $0.25 / $1.50 | 1,048,576 input tokens | JSON Schema subset | Designed for low latency and simple processing. Lower-cost candidate to evaluate for consistency on sparse sites and nuanced competitor comparisons. | $0.00395 |
| Anthropic Claude Haiku 5.5 | $0.10 / $0.50 for prompts up to 100K | 1M | Structured outputs | Designed for latency-sensitive extraction. Lowest estimated cost in this comparison and a candidate for a cross-provider evaluation. | $0.00140 |

Sources: [OpenAI GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini), [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing), [Gemini model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite), [Gemini structured outputs](https://ai.google.dev/gemini-api/docs/structured-output), [Claude Haiku 5.5](https://platform.claude.com/docs/en/models/haiku-5-5/overview), [Claude structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).

**Recommendation.** Start with OpenAI GPT-5.4 mini for its strict schema integration, bounded output cost, and capacity to synthesize several pages in one request. Budget approximately **$0.012 per analysis** and **10 to 30 seconds end to end** on responsive sites as a planning estimate. Website fetches, provider queues, and optional fallback can extend that. There are no measured cross-provider latency or accuracy results for this workload. Use [GPT-5.4](https://developers.openai.com/api/docs/models/gpt-5.4) as the optional same-provider fallback, estimated at $0.03950 for the same token budget before any cost from the first attempt.

Before changing models, evaluate the same representative websites across providers, including sparse sites and niche businesses. Compare quote accuracy, relevance of competitor suggestions, usefulness of SEO advice, schema success, p50/p95 latency, and cost from actual token counts. Keep extraction deterministic and use one provider call by default. For repeat traffic, consider a short-lived result cache keyed by the extracted content hash, prompt version, and model. Revalidate page content before serving an older result. Cache only data appropriate for the deployment.

## Tests and deployment

Run `python -m pytest -q` in the virtual environment. The tests use controlled website and provider responses and require no API key. See the [verification log](examples/verification.log) for the automated tests, local Uvicorn checks and live extraction results. A live smoke test requires outbound HTTPS and a working key for the selected provider.

Publish this directory as a public GitHub repository and connect it to [Render Blueprints](https://render.com/docs/infrastructure-as-code). The included [render.yaml](render.yaml) defines the web service. Supply the provider key in Render when creating the Blueprint. Once deployed, use the service's HTTPS origin for the live demo, append `/docs` for Swagger and `/link-analysis` for the API. Check both Swagger and a successful POST before submitting. For a publicly reachable paid API, configure an upstream request rate limit and a dedicated provider budget.

The applicant submission also requests LinkedIn and Instagram follows and profile links. The submission email should include the applicant's full name, demo and repository links, phone number, current location, preferred discussion date and time, and both profile links. The brief lists 27 November 2026 as the deadline.

## Submission details

The brief asks applicants to follow [Dxora Technologies on LinkedIn](https://www.linkedin.com/company/dxora-technologies) and [CREST on Instagram](https://www.instagram.com/crestspot/). Include both profile links in the submission.

Email recipient is hr@chivoxai.com. Use the subject "Your Name - Python Practical Link Analysis test review" and include the live demo URL, the Swagger URL, and the public repository along with the applicant details above.
