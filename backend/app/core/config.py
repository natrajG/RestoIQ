from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+psycopg://restaurant_app:local@localhost:5432/restaurant_platform"
    migration_database_url: str | None = None
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "local-development-secret-change-before-deploy-000000"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 480
    cookie_secure: bool = False
    camera_encryption_key: str = "local-camera-encryption-secret-change-before-deploy"
    vision_api_key: str = "local-vision-key-change-before-deploy"
    demo_admin_email: str = "admin@demo.local"
    demo_admin_password: str = "change-me-before-sharing"
    platform_admin_email: str | None = None
    platform_admin_password: str | None = None
    seed_demo: bool = False
    upload_dir: str = "./uploads"
    video_retention_days: int = 30
    resend_api_key: str | None = None
    mail_from: str | None = None
    feedback_notify_email: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    app_public_url: str = "http://localhost:8180"
    seller_legal_name: str = ""
    seller_gstin: str = ""
    seller_address: str = ""
    seller_state_code: str = ""
    seller_sac: str = "998314"
    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None
    razorpay_webhook_secret: str | None = None
    llm_provider: str = "none"
    llm_api_key: str | None = None
    llm_model: str | None = None


settings = Settings()


def is_development() -> bool:
    return settings.environment.strip().lower() == "development"


def validate_production_secrets() -> None:
    """Fail closed: every environment except an explicit "development" must use real secrets."""
    if is_development():
        return
    unsafe = {
        "JWT_SECRET": settings.jwt_secret,
        "CAMERA_ENCRYPTION_KEY": settings.camera_encryption_key,
        "VISION_API_KEY": settings.vision_api_key,
    }
    bad = [name for name, value in unsafe.items() if len(value) < 32 or "change-before-deploy" in value or value.startswith("local-")]
    if bad:
        raise RuntimeError(f"Production secrets must be independently generated (at least 32 characters): {', '.join(bad)}")
    if not settings.cookie_secure:
        raise RuntimeError("COOKIE_SECURE must be true outside development")
