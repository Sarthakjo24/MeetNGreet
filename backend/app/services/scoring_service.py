from collections.abc import Mapping
from typing import Any


class ScoringService:
    weights = {
        "communication": 0.45,
        "content": 0.45,
        "confidence": 0.10,
    }

    def score_answer(
        self,
        question_text: str,
        transcript: str,
        video_metrics: dict[str, float],
        llm_override: Mapping[str, Any] | None = None,
    ) -> dict:
        _ = question_text, transcript, video_metrics

        if not llm_override:
            raise ValueError(
                "OpenAI scoring is required. Set USE_OPENAI_EVAL=true and configure OPENAI_API_KEY."
            )

        communication = self._to_score_10(llm_override.get("communication_score"))
        content_raw = self._to_score_10(llm_override.get("content_score"))
        relevance = self._to_score_10(llm_override.get("relevance_score"), default=content_raw)
        confidence = self._to_score_10(llm_override.get("confidence_score"))

        # Content should strongly reflect topic relevance, not just answer length.
        content = (content_raw * 0.6) + (relevance * 0.4)
        if relevance <= 3.0:
            content = min(content, 3.5)
        elif relevance <= 5.0:
            content = min(content, 5.5)

        llm_final = llm_override.get("final_score")
        if llm_final is None:
            final = (
                communication * self.weights["communication"]
                + content * self.weights["content"]
                + confidence * self.weights["confidence"]
            )
        else:
            final = self._to_score_10(llm_final)
            # Guardrail: if relevance is low, do not allow very high final score.
            if relevance <= 3.0:
                final = min(final, 4.5)
            elif relevance <= 5.0:
                final = min(final, 6.5)

        feedback = str(llm_override.get("feedback") or "").strip()
        if not feedback:
            feedback = "Improve clarity, answer relevance, and confidence."

        strengths = self._to_points(
            llm_override.get("strengths"),
            fallback="Shows intent to address the question.",
        )
        weaknesses = self._to_points(
            llm_override.get("weaknesses"),
            fallback="Needs stronger structure, relevance, and specificity.",
        )

        return {
            "communication_score": round(communication, 2),
            "content_score": round(content, 2),
            "confidence_score": round(confidence, 2),
            "final_score": round(final, 2),
            "feedback": feedback,
            "strengths": strengths,
            "weaknesses": weaknesses,
        }

    def classify_score(self, score: float) -> str:
        if score <= 2.5:
            return "Below Average"
        if score <= 5.0:
            return "Average"
        if score < 7.5:
            return "Good"
        return "Excellent"

    def _to_score_10(self, value: Any, default: float = 0.0) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = default

        if 0.0 <= numeric <= 1.0:
            numeric *= 10

        return max(0.0, min(10.0, numeric))

    def _to_points(self, value: Any, fallback: str) -> list[str]:
        points: list[str] = []

        if isinstance(value, list):
            for item in value:
                text = str(item).strip()
                if text:
                    points.append(text)
        elif isinstance(value, str):
            text = value.strip()
            if text:
                points.append(text)

        if not points:
            return [fallback]

        deduped: list[str] = []
        seen: set[str] = set()
        for point in points:
            key = point.casefold()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(point)

        return deduped[:4]