from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SECRET_KEY: str = "foodtruck-super-secret-key-2024"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    DATABASE_URL: str = "sqlite:///./foodtruck.db"
    SUMATRA_PDF_PATH: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
