from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Gym-OS"
    environment: str = "dev"  # dev | test | prod
    database_url: str = "postgresql+psycopg://gymos:gymos@localhost:5432/gymos"

    jwt_secret: str = "dev-only-insecure-secret-change-me-0000"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    refresh_token_days: int = 30

    # Business timezone: DB session + server TZ. Day boundaries, peak hours, reports use this.
    timezone: str = "Asia/Kolkata"

    public_base_url: str = "https://gymos.manima.co.in"
    cors_origins: str = "http://localhost:3000"

    # SaaS billing
    trial_days: int = 14
    grace_days: int = 5

    # OTP
    otp_ttl_minutes: int = 5
    otp_dev_echo: bool = True  # return OTP in API response (dev only)

    # Notification providers: "log" (no-op, prints) or real provider names
    email_provider: str = "log"
    sms_provider: str = "log"
    whatsapp_provider: str = "log"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "Gym-OS <no-reply@manima.co.in>"

    rotating_qr_window_seconds: int = 30

    @property
    def is_prod(self) -> bool:
        return self.environment == "prod"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.is_prod:
        if s.jwt_secret.startswith("dev-only") or len(s.jwt_secret) < 32:
            raise RuntimeError("Set a strong JWT_SECRET (32+ chars) in production")
        s.otp_dev_echo = False
    return s
