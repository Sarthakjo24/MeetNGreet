import json
import time
from typing import Any

from ..config import settings


class LLMScoringService:
    def __init__(self) -> None:
        self.client = None

        if settings.use_openai_eval and settings.openai_api_key:
            try:
                from openai import OpenAI

                self.client = OpenAI(api_key=settings.openai_api_key)
            except Exception:
                self.client = None

    def evaluate(
        self,
        question_text: str,
        transcript: str,
        video_metrics: dict[str, float],
    ) -> dict[str, Any] | None:
        if not self.client:
            return None

        prompt = (
            "You are a strict interview evaluator. Evaluate ONE candidate response to ONE question and return JSON only. "
            "The transcript may be English, Hindi (Devanagari), or mixed Hinglish. "
            "Evaluate semantic meaning and relevance regardless of language/script. "
            "Do not penalize non-English words by themselves. "
            "Score 0-10 with this rubric: Communication 45%, Content 45%, Confidence 10%. "
            "For CONTENT, prioritize relevance to the asked topic over length. "
            "A long but off-topic answer must receive a low content score. "
            "If relevance is poor, content_score cannot be high. "
            "Use these dimensions: "
            "Communication (clarity, structure, coherence, conciseness), "
            "Content (topic relevance, correctness, depth, examples), "
            "Confidence (delivery cues using video_metrics only as a weak signal). "
            "Penalize repetition loops, rambling, contradiction, and vague generic filler. "
            "Do not reward length by itself. "
            "If transcript is empty/near-empty, scores should be very low. "
            "Return strict JSON keys: communication_score, content_score, relevance_score, confidence_score, final_score, feedback, strengths, weaknesses. "
            "relevance_score is 0-10 for topic alignment. "
            "feedback must be 2-3 actionable sentences mentioning relevance if weak. "
            "strengths and weaknesses must be concise arrays of 2-4 bullet-like strings each."
        )

        user_content = {
            "question": question_text,
            "transcript": transcript,
            "video_metrics": video_metrics,
            "weights": {
                "communication": 0.45,
                "content": 0.45,
                "confidence": 0.10,
            },
        }

        try:
            retry_delays = [0.0, 1.0, 2.5]
            for idx, delay_seconds in enumerate(retry_delays):
                if delay_seconds > 0:
                    time.sleep(delay_seconds)

                try:
                    response = self.client.chat.completions.create(
                        model=settings.openai_eval_model,
                        temperature=0.0,
                        response_format={"type": "json_object"},
                        messages=[
                            {"role": "system", "content": prompt},
                            {"role": "user", "content": json.dumps(user_content)},
                        ],
                        timeout=60,
                    )
                    raw = response.choices[0].message.content
                    if not raw:
                        continue

                    data = json.loads(raw)
                    sanitized = self._sanitize(data)
                    if sanitized:
                        return sanitized
                except Exception:
                    if idx >= len(retry_delays) - 1:
                        raise

            return None
        except Exception:
            return None

    def _sanitize(self, data: dict[str, Any]) -> dict[str, Any] | None:
        communication = self._to_score_10(data.get("communication_score"))
        content = self._to_score_10(data.get("content_score"))
        relevance = self._to_score_10(data.get("relevance_score"))
        confidence = self._to_score_10(data.get("confidence_score"))

        if communication is None or content is None or relevance is None or confidence is None:
            return None

        final_score = self._to_score_10(data.get("final_score"))
        if final_score is None:
            adjusted_content = (content * 0.6) + (relevance * 0.4)
            final_score = (
                communication * 0.45
                + adjusted_content * 0.45
                + confidence * 0.10
            )

        feedback = str(data.get("feedback") or "").strip()
        if not feedback:
            feedback = "Give a clearer, more relevant answer with concrete examples and stronger structure."

        strengths = self._to_points(
            data.get("strengths"),
            fallback="Shows intent to answer the question.",
        )
        weaknesses = self._to_points(
            data.get("weaknesses"),
            fallback="Needs clearer structure and stronger relevance to the asked topic.",
        )

        return {
            "communication_score": round(communication, 2),
            "content_score": round(content, 2),
            "relevance_score": round(relevance, 2),
            "confidence_score": round(confidence, 2),
            "final_score": round(final_score, 2),
            "feedback": feedback,
            "strengths": strengths,
            "weaknesses": weaknesses,
        }

    def _to_score_10(self, value: Any) -> float | None:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None

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
