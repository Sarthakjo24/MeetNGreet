from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from ..config import settings


class MediaStorageService:
    _chunk_size_bytes = 1024 * 1024

    def __init__(self, media_dir: str | None = None) -> None:
        self.media_dir = Path(media_dir or settings.media_dir)
        self.media_dir.mkdir(parents=True, exist_ok=True)

    async def store_media(
        self,
        session_id: str,
        question_id: str,
        upload_file: UploadFile,
    ) -> tuple[str, str, str]:
        ext = Path(upload_file.filename or "response.webm").suffix or ".webm"

        file_name = (
            f"{session_id}_{question_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}{ext}"
        )
        file_path = self.media_dir / file_name

        with file_path.open("wb") as output:
            while True:
                chunk = await upload_file.read(self._chunk_size_bytes)
                if not chunk:
                    break
                output.write(chunk)

        await upload_file.close()

        mime = upload_file.content_type or "video/webm"
        return str(file_path), file_name, mime
