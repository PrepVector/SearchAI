"""Pydantic schemas — the API contracts between frontend and pipeline."""
from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class GenerationOptions(BaseModel):
    format: Literal["auto", "research_paper", "strategic_briefing", "decision_memo",
                    "technical_field_guide", "mathematical_explainer",
                    "security_operations_report", "implementation_playbook",
                    "comparative_analysis", "historical_timeline",
                    "current_intelligence_briefing"] = "auto"
    current_findings: bool = True
    web_research: bool = True
    image_count: int = Field(default=5, ge=0, le=12)


class OutlineSection(BaseModel):
    id: str
    title: str
    goal: str = ""
    subpoints: list[str] = Field(default_factory=list)
    key_questions: list[str] = Field(default_factory=list)
    bridge: str = ""


class Outline(BaseModel):
    layout: str = "auto"
    title: str
    narrative_thread: str = ""
    sections: list[OutlineSection]


class OutlineRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=600)
    options: GenerationOptions = Field(default_factory=GenerationOptions)


class OutlineResponse(BaseModel):
    topic: str
    analysis: dict[str, Any]
    outline: Outline
    trace: list[dict[str, Any]]


class GenerateRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=600)
    outline: Outline
    analysis: Optional[dict[str, Any]] = None
    options: GenerationOptions = Field(default_factory=GenerationOptions)


class ArticleImage(BaseModel):
    slot: int
    url: str                      # http(s) URL or data: URI (SVG fallback visual)
    caption: str
    explanation: str = ""
    source_label: str = ""
    kind: Literal["reference", "generated", "fallback_visual"] = "reference"
    section_id: str = ""


class ArticleSection(BaseModel):
    id: str
    title: str
    markdown: str
    pull_quote: Optional[str] = None


class Reference(BaseModel):
    title: str
    url: str = ""
    source: str = ""
    year: Optional[int] = None
    doi: str = ""


class Article(BaseModel):
    topic: str
    title: str
    layout: str
    abstract: str
    executive_answer: str
    key_takeaways: list[str] = Field(default_factory=list)
    sections: list[ArticleSection]
    images: list[ArticleImage] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)


class Diagnostics(BaseModel):
    agents_used: list[str]
    validation_status: str
    outline_alignment_score: float
    source_credibility_status: str
    currentness_status: str
    image_relevance_status: str
    warnings: list[str] = Field(default_factory=list)
    trace: list[dict[str, Any]] = Field(default_factory=list)


class GenerateResponse(BaseModel):
    article: Article
    diagnostics: Diagnostics


class DocxExportRequest(BaseModel):
    article: Article


class PdfExportRequest(BaseModel):
    html: str
    title: str = "SEARCH AI Article"
