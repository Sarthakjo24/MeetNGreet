import json
import random
from pathlib import Path

from ..config import settings


class QuestionService:
    def __init__(self, question_bank_path: str | None = None) -> None:
        self.question_bank_path = Path(question_bank_path or settings.question_bank_path)

    def _load_question_bank(self) -> dict:
        if not self.question_bank_path.exists():
            raise FileNotFoundError(f"Question bank not found: {self.question_bank_path}")

        with self.question_bank_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def select_questions(
        self,
        selection_mode: str | None = None,
        question_count: int | None = None,
    ) -> list[dict]:
        payload = self._load_question_bank()

        mode = selection_mode or settings.question_selection_mode or payload.get("selection_mode", "fixed")
        count = question_count or settings.question_count or payload.get("question_count", 5)

        questions = payload.get("questions", [])
        if not questions:
            raise ValueError("No questions configured in question bank")

        if mode == "mixed":
            always_ids = set(payload.get("always_include_ids", []))
            always = [q for q in questions if q["id"] in always_ids]
            pool = [q for q in questions if q["id"] not in always_ids]

            needed_random = max(count - len(always), 0)
            random_selected = random.sample(pool, k=min(needed_random, len(pool)))
            selected = always + random_selected
        else:
            fixed_ids = payload.get("fixed_question_ids")
            if fixed_ids:
                selected = [q for q in questions if q["id"] in set(fixed_ids)]
                selected.sort(key=lambda x: fixed_ids.index(x["id"]))
            else:
                fixed = [q for q in questions if q.get("type", "fixed") == "fixed"]
                selected = fixed or questions

        if len(selected) < count:
            raise ValueError(
                f"Insufficient question count. Required {count}, found {len(selected)} for mode '{mode}'."
            )

        return selected[:count]
