"""Narrow Vision port: graph code cannot import vendor HTTP or image codecs."""

from __future__ import annotations

from typing import Protocol

from app.providers.vision.dto import VisionMealRequest, VisionMealResult


class VisionModelProvider(Protocol):
    async def analyze_meal_image(self, request: VisionMealRequest) -> VisionMealResult: ...
