"""Shared configuration loaded from environment variables."""

import os


class Settings:
    """Simple settings from env vars — no validation (intentionally loose)."""

    def __init__(self):
        self.database_url: str = os.getenv("DATABASE_URL", "sqlite:///./local.db")
        self.service_name: str = os.getenv("SERVICE_NAME", "unknown")
        self.service_port: int = int(os.getenv("SERVICE_PORT", "8000"))

        # JWT
        self.jwt_secret: str = os.getenv("JWT_SECRET", "super-secret-jwt-key-do-not-use-in-production")
        self.jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
        self.jwt_expiry_minutes: int = int(os.getenv("JWT_EXPIRY_MINUTES", "60"))
        self.jwt_refresh_expiry_days: int = int(os.getenv("JWT_REFRESH_EXPIRY_DAYS", "30"))

        # RabbitMQ
        self.rabbitmq_host: str = os.getenv("RABBITMQ_HOST", "localhost")
        self.rabbitmq_port: int = int(os.getenv("RABBITMQ_PORT", "5672"))
        self.rabbitmq_user: str = os.getenv("RABBITMQ_USER", "guest")
        self.rabbitmq_password: str = os.getenv("RABBITMQ_PASSWORD", "guest")

        # Internal service URLs
        self.auth_service_url: str = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
        self.user_service_url: str = os.getenv("USER_SERVICE_URL", "http://localhost:8002")
        self.project_service_url: str = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8003")
        self.billing_service_url: str = os.getenv("BILLING_SERVICE_URL", "http://localhost:8004")
        self.payment_service_url: str = os.getenv("PAYMENT_SERVICE_URL", "http://localhost:8005")
        self.notification_service_url: str = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8006")
        self.reporting_service_url: str = os.getenv("REPORTING_SERVICE_URL", "http://localhost:8007")


settings = Settings()
