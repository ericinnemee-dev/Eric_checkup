from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "dev"
    database_url: str = "sqlite:///./hms.db"
    jwt_secret: str = "dev-secret-change-me"
    jwt_alg: str = "HS256"
    jwt_ttl_min: int = 60
    seed_dev_users: bool = True

    planner_seed_username: str = "planner"
    planner_seed_password: str = "planner123"
    viewer_seed_username: str = "viewer"
    viewer_seed_password: str = "viewer123"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        case_sensitive=False,
    )


settings = Settings()
