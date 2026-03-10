from typing import Dict
from ai_core.models.chat.llm_factory import LLMFactory


class LLMRouter:
    """
    Enterprise-grade dynamic LLM router.
    """

    def __init__(self, config):
        self.config = config
        self._models: Dict[str, object] = {}

    # =====================================================
    # Complexity Scoring
    # =====================================================

    def _score_complexity(self, query: str) -> int:
        score = 0
        q = query.lower()

        if len(query) > 300:
            score += 3
        elif len(query) > 150:
            score += 2
        elif len(query) > 80:
            score += 1

        if query.count("?") > 1:
            score += 2

        analytical_keywords = [
            "phân tích",
            "so sánh",
            "tại sao",
            "giải thích",
            "chứng minh",
            "đánh giá",
            "chiến lược",
            "tổng hợp",
        ]

        for kw in analytical_keywords:
            if kw in q:
                score += 2
                break

        return score

    # =====================================================
    # Lazy Loader
    # =====================================================

    def _get_or_create_model(self, model_name, temperature):
        key = f"{model_name}:{temperature}"

        if key in self._models:
            return self._models[key]

        model = LLMFactory.create_chat_model(
            model_name=model_name,
            temperature=temperature,
        )

        self._models[key] = model
        return model

    # =====================================================
    # Public API
    # =====================================================

    def route(self, query: str):
        score = self._score_complexity(query)

        if score <= 1:
            return self._get_or_create_model(
                self.config.LIGHT_MODEL,
                self.config.LIGHT_TEMPERATURE,
            )

        if score <= 4:
            return self._get_or_create_model(
                self.config.MEDIUM_MODEL,
                self.config.MEDIUM_TEMPERATURE,
            )

        return self._get_or_create_model(
            self.config.HEAVY_MODEL,
            self.config.HEAVY_TEMPERATURE,
        )

    def get_role_model(self, model_name: str, temperature: float):
        return self._get_or_create_model(model_name, temperature)