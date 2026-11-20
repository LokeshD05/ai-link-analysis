from app.schemas import LinkResponse
from app.services.llm_service import analyze_pages
from app.services.website_extractor import extract_website


async def analyze_website(url: str) -> LinkResponse:
    pages = await extract_website(url)
    result = await analyze_pages(pages)
    return LinkResponse(
        website=url,
        sources={f"page_{index}": page.url for index, page in enumerate(pages, 1)},
        **result.model_dump(),
    )
