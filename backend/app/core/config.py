import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "British Auction RFQ System"
    API_V1_PREFIX: str = "/api/v1"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./rfq_auction.db"
    )
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    SCHEDULER_ENABLED: bool = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
    SCHEDULER_INTERVAL_SECONDS: int = int(os.getenv("SCHEDULER_INTERVAL_SECONDS", "5"))

    class Config:
        case_sensitive = True


settings = Settings()
