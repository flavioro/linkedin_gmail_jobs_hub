from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LinkedIn Gmail Jobs Hub"
    app_env: str = "development"
    api_v1_str: str = "/api/v1"
    api_key: str = "change-me"
    db_url: str = "sqlite:///./data/jobs_hub.db"
    google_token_file: str = "./secrets/token.json"
    google_credentials_file: str = "./secrets/credentials.json"
    gmail_query: str = ""
    gmail_label: str = "linkedin_jobs"
    gmail_sender_filters: str = "jobs-listings@linkedin.com,jobs-noreply@linkedin.com,jobalerts-noreply@linkedin.com,linkedin@e.linkedin.com,jobs-listings@e.linkedin.com"
    allowed_sender_contains: str = "linkedin.com"
    gmail_subject_terms: str = "vaga,vagas,job,jobs,oportunidade,oportunidades"
    gmail_newer_than_days: int = 7
    gmail_max_results: int = 50
    gmail_user_id: str = "me"
    default_log_level: str = "INFO"
    log_file: str = "./logs/app.log"
    log_max_bytes: int = 1048576
    log_backup_count: int = 3
    enable_gmail_sync: bool = True
    enable_broad_linkedin_fallback: bool = True
    retry_max_attempts: int = 3
    retry_base_delay_seconds: float = 1.0
    retry_jitter_seconds: float = 0.25

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
