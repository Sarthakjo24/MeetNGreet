import os
from pathlib import Path

import uvicorn


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def main() -> None:
    root_dir = Path(__file__).resolve().parent
    app_dir = root_dir / "backend" / "app"

    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "8000"))
    reload_enabled = _to_bool(os.getenv("APP_RELOAD"), default=True)

    uvicorn.run(
        "backend.app.main:app",
        host=host,
        port=port,
        reload=reload_enabled,
        reload_dirs=[str(app_dir)],
    )


if __name__ == "__main__":
    main()
