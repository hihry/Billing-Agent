"""
Schemas for the narrative layer's output. NarrativeContent is what BOTH
the LLM path and the fallback-template path produce — the rest of the
system (storage, API) never needs to know which one generated it.
"""

from __future__ import annotations

from pydantic import BaseModel


class CitedFigure(BaseModel):
    """Maps one number in the narrative text back to the report field it
    came from. This is exactly what the frontend's 'Traced Figures' panel
    renders — no extra mapping logic needed there."""
    value: str
    source_field: str


class NarrativeContent(BaseModel):
    narrative: str
    cited_figures: list[CitedFigure]