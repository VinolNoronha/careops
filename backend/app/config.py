from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    supabase_url: str
    supabase_jwt_secret: str
    database_url: str
    gemini_api_key: str

    class Config:
        env_file = ".env"

settings = Settings()
print("LOADED DATABASE_URL:", repr(settings.database_url))