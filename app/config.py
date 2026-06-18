from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SECRET_KEY: str = "foodtruck-super-secret-key-2024"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    DATABASE_URL: str = "postgresql://postgres:fNCryRyWoCFSjoipTuRAxYyZvnJbaMtF@postgres.railway.internal:5432/railway"
    SUMATRA_PDF_PATH: str = ""
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"

    class Config:
        env_file = ".env"


settings = Settings()
