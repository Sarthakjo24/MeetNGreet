from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MeetnGreet Automation API"
    app_version: str = "0.1.0"

    use_local_db: bool = Field(default=True, alias="USE_LOCAL_DB")
    local_db_path: str = Field(
        default="./backend/storage/local_app.db",
        alias="LOCAL_DB_PATH",
    )
    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    mysql_host: str = Field(default="127.0.0.1", alias="MYSQL_HOST")
    mysql_port: int = Field(default=3306, alias="MYSQL_PORT")
    mysql_user: str = Field(default="root", alias="MYSQL_USER")
    mysql_password: str = Field(default="", alias="MYSQL_PASSWORD")
    mysql_database: str = Field(default="auth_system", alias="MYSQL_DATABASE")

    media_dir: str = Field(default="./backend/storage/media", alias="MEDIA_DIR")

    question_bank_path: str = Field(
        default="./backend/app/data/questions.json",
        alias="QUESTION_BANK_PATH",
    )
    question_selection_mode: str = Field(default="mixed", alias="QUESTION_SELECTION_MODE")
    question_count: int = Field(default=5, alias="QUESTION_COUNT")

    use_openai_eval: bool = Field(default=True, alias="USE_OPENAI_EVAL")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_eval_model: str = Field(default="gpt-4o-mini", alias="OPENAI_EVAL_MODEL")
    openai_transcribe_model: str = Field(
        default="gpt-4o-mini-transcribe",
        alias="OPENAI_TRANSCRIBE_MODEL",
    )

    use_faster_whisper: bool = Field(default=True, alias="USE_FASTER_WHISPER")
    faster_whisper_model: str = Field(default="small", alias="FASTER_WHISPER_MODEL")
    faster_whisper_device: str = Field(default="cpu", alias="FASTER_WHISPER_DEVICE")
    faster_whisper_compute_type: str = Field(
        default="int8",
        alias="FASTER_WHISPER_COMPUTE_TYPE",
    )

    session_secret: str = Field(default="change-me-session-secret", alias="SESSION_SECRET")
    session_algorithm: str = Field(default="HS256", alias="SESSION_ALGORITHM")
    session_ttl_minutes: int = Field(default=720, alias="SESSION_TTL_MINUTES")
    session_cookie_name: str = Field(default="meetngreet_session", alias="SESSION_COOKIE_NAME")
    session_cookie_secure: bool = Field(default=False, alias="SESSION_COOKIE_SECURE")
    session_cookie_samesite: str = Field(default="lax", alias="SESSION_COOKIE_SAMESITE")
    session_cookie_domain: str | None = Field(default=None, alias="SESSION_COOKIE_DOMAIN")

    auth0_domain: str | None = Field(default=None, alias="AUTH0_DOMAIN")
    auth0_client_id: str | None = Field(default=None, alias="AUTH0_CLIENT_ID")
    auth0_client_secret: str | None = Field(default=None, alias="AUTH0_CLIENT_SECRET")
    auth0_callback_url: str = Field(
        default="http://127.0.0.1:8000/api/auth/callback",
        alias="AUTH0_CALLBACK_URL",
    )
    auth0_logout_url: str = Field(
        default="http://127.0.0.1:8000/",
        alias="AUTH0_LOGOUT_URL",
    )
    auth0_google_connection: str = Field(
        default="google-oauth2",
        alias="AUTH0_GOOGLE_CONNECTION",
    )
    auth0_microsoft_connection: str = Field(
        default="windowslive",
        alias="AUTH0_MICROSOFT_CONNECTION",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
