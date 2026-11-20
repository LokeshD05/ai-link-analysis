from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LinkRequest(Contract):
    url: HttpUrl


class Brand(Contract):
    name: str
    category: str
    summary: str
    products_and_services: list[str]


class Competitor(Contract):
    name: str
    main_service: str
    target_market: str
    overlap: str
    potential_strengths: list[str]
    potential_gaps: list[str]


class CompetitorAnalysis(Contract):
    brand_overview: str
    target_market: str
    competitors: list[Competitor]
    strengths: list[str]
    opportunities: list[str]


class SearchQuery(Contract):
    query: str
    platforms: list[Literal["Google", "Facebook", "Instagram", "LinkedIn", "X"]] = Field(min_length=1)
    intent: str
    business_relevance: str
    target_audience: str


class SEO(Contract):
    primary_keyword: str
    secondary_keywords: list[str]
    long_tail_keywords: list[str]
    business_keywords: list[str]
    recommended_title: str
    title_structure: str
    meta_description: str
    supporting_content: list[str]


class Service(Contract):
    name: str
    description: str
    target_industry: str
    target_customer: str
    main_benefit: str
    basis: Literal["website", "inferred_recommendation"]
    evidence_id: str | None
    evidence_excerpt: str | None


class Audience(Contract):
    primary_audience: list[str]
    secondary_audience: list[str]
    industries: list[str]
    business_types: list[str]
    customer_profiles: list[str]
    geography: list[str]
    customer_needs: list[str]
    customer_interests: list[str]
    marketing_segments: list[str]


class Analysis(Contract):
    competitor_analysis: CompetitorAnalysis
    target_search_queries: list[SearchQuery] = Field(min_length=5, max_length=5)
    seo_improvements: SEO
    top_services: list[Service] = Field(max_length=5)
    target_audience: Audience


class ModelResult(Contract):
    brand: Brand
    analysis: Analysis


class LinkResponse(ModelResult):
    success: Literal[True] = True
    website: HttpUrl
    sources: dict[str, str]
    competitor_basis: Literal["ai_generated_suggestions"] = "ai_generated_suggestions"


class ErrorResponse(Contract):
    success: Literal[False] = False
    error: str
    detail: str
