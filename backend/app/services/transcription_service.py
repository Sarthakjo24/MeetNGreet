from pathlib import Path
from tempfile import NamedTemporaryFile

from ..config import settings


ALLOWED_LANGUAGE_CODES = {"en", "hi"}
VIDEO_CONTAINER_EXTENSIONS = {".webm", ".mp4", ".mkv", ".mov", ".avi", ".mpeg", ".mpg"}


class TranscriptionService:
    def __init__(self) -> None:
        self.whisper_model = None
        self.whisper_model_ready = False
        self.whisper_model_failed = False
        self.openai_client = None

        if settings.openai_api_key:
            try:
                from openai import OpenAI

                self.openai_client = OpenAI(api_key=settings.openai_api_key)
            except Exception:
                self.openai_client = None

    def transcribe(self, media_bytes: bytes, file_name: str, transcript_hint: str | None = None) -> str:
        if not media_bytes:
            return self._prepare_candidate(transcript_hint)

        suffix = Path(file_name).suffix or ".webm"
        temp_path: Path | None = None
        hint_candidate = self._prepare_candidate(transcript_hint)

        try:
            with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(media_bytes)
                temp_path = Path(tmp.name)

            candidates: list[tuple[str, str]] = []

            # On some Windows setups, Faster-Whisper crashes on video containers (e.g. webm/mp4).
            # Keep Faster-Whisper for audio files only, and use OpenAI/hint fallback for video uploads.
            if suffix.lower() not in VIDEO_CONTAINER_EXTENSIONS:
                whisper_model = self._get_whisper_model()
                if whisper_model:
                    whisper_text = self._prepare_candidate(
                        self._transcribe_with_faster_whisper(temp_path, whisper_model)
                    )
                    if whisper_text:
                        candidates.append(("whisper", whisper_text))

            if self.openai_client:
                openai_text = self._prepare_candidate(self._transcribe_with_openai(temp_path))
                if openai_text:
                    candidates.append(("openai", openai_text))

            if hint_candidate:
                candidates.append(("hint", hint_candidate))

            best = self._pick_best_transcript(candidates)
            return best or hint_candidate or ""
        except Exception:
            return hint_candidate or ""
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink(missing_ok=True)

    def _get_whisper_model(self):
        if not settings.use_faster_whisper:
            return None
        if self.whisper_model_ready:
            return self.whisper_model
        if self.whisper_model_failed:
            return None

        compute_candidates = [
            settings.faster_whisper_compute_type,
            "int8_float32",
            "float32",
        ]
        tried: set[str] = set()

        try:
            from faster_whisper import WhisperModel
        except Exception:
            self.whisper_model_failed = True
            return None

        for compute_type in compute_candidates:
            if compute_type in tried:
                continue
            tried.add(compute_type)
            try:
                self.whisper_model = WhisperModel(
                    model_size_or_path=settings.faster_whisper_model,
                    device=settings.faster_whisper_device,
                    compute_type=compute_type,
                )
                self.whisper_model_ready = True
                return self.whisper_model
            except Exception:
                continue

        self.whisper_model_failed = True
        return None

    def _prepare_candidate(self, text: str | None) -> str:
        cleaned = self.clean_text(text)
        if not cleaned:
            return ""

        cleaned = self._to_hinglish(cleaned)
        cleaned = self.clean_text(cleaned)
        if not cleaned:
            return ""

        if self._looks_like_unsupported_marker(cleaned):
            return ""
        if not self._is_allowed_script_text(cleaned):
            return ""
        return cleaned

    def _pick_best_transcript(self, candidates: list[tuple[str, str]]) -> str:
        if not candidates:
            return ""

        best_text = ""
        best_score = -1.0

        for source, text in candidates:
            if not text:
                continue

            words = text.split()
            word_count = len(words)

            # Prefer server-side transcription.
            source_bonus = 0.05 if source == "openai" else 0.03
            length_bonus = min(word_count, 60) / 600.0
            quality_penalty = 0.25 if self._is_low_quality(text) else 0.0

            score = source_bonus + length_bonus - quality_penalty
            if score > best_score:
                best_score = score
                best_text = text

        return best_text

    def _transcribe_with_openai(self, temp_path: Path) -> str:
        if not self.openai_client:
            return ""

        try:
            with temp_path.open("rb") as audio_file:
                transcript_obj = self.openai_client.audio.transcriptions.create(
                    model=settings.openai_transcribe_model,
                    file=audio_file,
                    prompt=(
                        "Transcribe spoken audio only in Hindi or English. "
                         "Return transcript in Hinglish (Roman script) only. "
                        "Transliterate Hindi words into natural Roman Hindi. "
                        "Do not output Devanagari or any non-Latin script. "
                        "If speech is in any other language, return an empty transcript. "
                        "Ignore repeated partial fragments and filler noise."
                    ),
                )
            text = getattr(transcript_obj, "text", "") or ""
            return self.clean_text(text)
        except Exception:
            return ""

    def _transcribe_with_faster_whisper(self, temp_path: Path, whisper_model) -> str:
        if not whisper_model:
            return ""

        try:
            segments, info = whisper_model.transcribe(
                str(temp_path),
                task="transcribe",
                beam_size=5,
                best_of=5,
                temperature=0.0,
                vad_filter=True,
                condition_on_previous_text=False,
            )

            detected_language = (getattr(info, "language", "") or "").strip().lower()
            if detected_language and detected_language not in ALLOWED_LANGUAGE_CODES:
                return ""

            text = " ".join(
                segment.text.strip()
                for segment in segments
                if segment.text and segment.text.strip()
            ).strip()
            return self.clean_text(text)
        except Exception:
            return ""

    @classmethod
    def clean_text(cls, text: str | None) -> str:
        normalized = cls._normalize_whitespace(text)
        if not normalized:
            return ""

        collapsed = cls._collapse_repeated_ngrams(normalized)
        return cls._normalize_whitespace(collapsed)

    @staticmethod
    def _normalize_whitespace(text: str | None) -> str:
        if not text:
            return ""
        return " ".join(str(text).split())

    @staticmethod
    def _collapse_repeated_ngrams(text: str) -> str:
        words = text.split(" ")
        if len(words) < 2:
            return text

        max_n = min(12, len(words) // 2)
        changed = True

        while changed:
            changed = False
            for n in range(max_n, 0, -1):
                i = 0
                compact: list[str] = []

                while i < len(words):
                    if i + (2 * n) <= len(words) and words[i : i + n] == words[i + n : i + (2 * n)]:
                        segment = words[i : i + n]
                        compact.extend(segment)
                        i += n

                        while i + n <= len(words) and words[i : i + n] == segment:
                            i += n

                        changed = True
                        continue

                    compact.append(words[i])
                    i += 1

                words = compact

        deduped: list[str] = []
        for word in words:
            if deduped and deduped[-1].lower() == word.lower():
                continue
            deduped.append(word)

        return " ".join(deduped)

    @staticmethod
    def _looks_like_unsupported_marker(text: str) -> bool:
        lower = text.casefold()
        markers = (
            "unsupported language",
            "cannot transcribe",
            "unable to transcribe",
            "only hindi or english",
        )
        return any(marker in lower for marker in markers)

    @classmethod
    def _to_hinglish(cls, text: str) -> str:
        if not text:
            return ""

        if not any(0x0900 <= ord(ch) <= 0x097F for ch in text):
            return text

        return cls._transliterate_devanagari_basic(text)

    @staticmethod
    def _transliterate_devanagari_basic(text: str) -> str:
        vowels = {
            "अ": "a", "आ": "aa", "इ": "i", "ई": "ii", "उ": "u", "ऊ": "uu",
            "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "ऋ": "ri",
        }
        consonants = {
            "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n",
            "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "ny",
            "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
            "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
            "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
            "य": "y", "र": "r", "ल": "l", "व": "v", "श": "sh", "ष": "sh", "स": "s", "ह": "h",
            "क़": "q", "ख़": "kh", "ग़": "gh", "ज़": "z", "फ़": "f", "ड़": "r", "ढ़": "rh",
        }
        matras = {
            "ा": "aa", "ि": "i", "ी": "ii", "ु": "u", "ू": "uu",
            "े": "e", "ै": "ai", "ो": "o", "ौ": "au", "ृ": "ri",
        }
        marks = {"ं": "n", "ँ": "n", "ः": "h", "़": ""}

        out: list[str] = []
        i = 0

        while i < len(text):
            ch = text[i]

            if ch in vowels:
                out.append(vowels[ch])
                i += 1
                continue

            if ch in consonants:
                base = consonants[ch]
                nxt = text[i + 1] if (i + 1) < len(text) else ""

                if nxt == "्":
                    out.append(base)
                    i += 2
                    continue

                if nxt in matras:
                    out.append(base + matras[nxt])
                    i += 2
                    continue

                if nxt in marks:
                    out.append(base + "a" + marks[nxt])
                    i += 2
                    continue

                out.append(base + "a")
                i += 1
                continue

            if ch in matras:
                out.append(matras[ch])
                i += 1
                continue

            if ch in marks:
                out.append(marks[ch])
                i += 1
                continue

            if ch == "्":
                i += 1
                continue

            out.append(ch)
            i += 1

        return "".join(out)

    @staticmethod
    def _is_allowed_script_text(text: str) -> bool:
        for ch in text:
            if not ch.isalpha():
                continue

            code = ord(ch)
            is_latin_ascii = (65 <= code <= 90) or (97 <= code <= 122)
            if not is_latin_ascii:
                return False

        return True

    @staticmethod
    def _is_low_quality(text: str) -> bool:
        words = text.split()
        if len(words) < 3:
            return True

        lower_words = [w.casefold() for w in words]
        unique_ratio = len(set(lower_words)) / len(lower_words)
        if len(words) >= 20 and unique_ratio < 0.22:
            return True

        longest_repeat = 1
        current_repeat = 1
        for idx in range(1, len(lower_words)):
            if lower_words[idx] == lower_words[idx - 1]:
                current_repeat += 1
                longest_repeat = max(longest_repeat, current_repeat)
            else:
                current_repeat = 1

        if longest_repeat >= 6:
            return True

        return False
