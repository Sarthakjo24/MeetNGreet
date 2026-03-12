from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MeetnGreet Automation API"
    app_version: str = "0.1.0"
    app_env: str = Field(default="development", alias="APP_ENV")

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
    openai_eval_max_concurrent: int = Field(default=2, alias="OPENAI_EVAL_MAX_CONCURRENT")
    evaluation_max_workers: int = Field(default=4, alias="EVAL_MAX_WORKERS")
    redis_url: str = Field(default="redis://127.0.0.1:6379/0", alias="REDIS_URL")
    evaluation_queue_name: str = Field(default="evaluation", alias="EVAL_QUEUE_NAME")
    evaluation_job_timeout: int = Field(default=900, alias="EVAL_JOB_TIMEOUT")
    evaluation_job_ttl: int = Field(default=3600, alias="EVAL_JOB_TTL")
    evaluation_failure_ttl: int = Field(default=3600, alias="EVAL_FAILURE_TTL")
    evaluation_requeue_enabled: bool = Field(default=True, alias="EVAL_REQUEUE_ENABLED")
    evaluation_requeue_interval_seconds: int = Field(
        default=60,
        alias="EVAL_REQUEUE_INTERVAL_SECONDS",
    )
    evaluation_requeue_batch_size: int = Field(default=25, alias="EVAL_REQUEUE_BATCH_SIZE")
    evaluation_requeue_lock_ttl_seconds: int = Field(
        default=55,
        alias="EVAL_REQUEUE_LOCK_TTL_SECONDS",
    )
    evaluation_requeue_max_attempts: int = Field(default=5, alias="EVAL_REQUEUE_MAX_ATTEMPTS")
    evaluation_requeue_attempt_ttl_seconds: int = Field(
        default=86400,
        alias="EVAL_REQUEUE_ATTEMPT_TTL_SECONDS",
    )
    healthcheck_openai: bool = Field(default=False, alias="HEALTHCHECK_OPENAI")
    healthcheck_openai_timeout_seconds: int = Field(
        default=5,
        alias="HEALTHCHECK_OPENAI_TIMEOUT_SECONDS",
    )
    rq_failed_job_alert_threshold: int = Field(
        default=10,
        alias="RQ_FAILED_JOB_ALERT_THRESHOLD",
    )
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

    @model_validator(mode="after")
    def _validate_security_settings(self):
        allowed_samesite = {"lax", "strict", "none"}
        samesite = str(self.session_cookie_samesite or "").strip().lower()
        if samesite not in allowed_samesite:
            raise ValueError("SESSION_COOKIE_SAMESITE must be one of: lax, strict, none.")
        if samesite == "none" and not self.session_cookie_secure:
            raise ValueError("SESSION_COOKIE_SAMESITE=none requires SESSION_COOKIE_SECURE=true.")
        self.session_cookie_samesite = samesite

        env = str(self.app_env or "").strip().lower()
        if env in {"prod", "production"}:
            if not self.session_secret or self.session_secret == "change-me-session-secret":
                raise ValueError("SESSION_SECRET must be set to a strong value in production.")
            if len(self.session_secret) < 32:
                raise ValueError("SESSION_SECRET must be at least 32 characters long.")
            if not self.session_cookie_secure:
                raise ValueError("SESSION_COOKIE_SECURE must be true in production.")
            if not (self.session_cookie_domain or "").strip():
                raise ValueError("SESSION_COOKIE_DOMAIN must be set in production.")
            self.session_cookie_domain = self.session_cookie_domain.strip()
        return self

settings = Settings()
