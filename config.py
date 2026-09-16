from pathlib import Path
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    #GitHub settings
    github_personal_access_token: SecretStr
    github_owner: str
    github_repo: str
    github_branch: str
    github_files: list[str]
    
    #Model and vector store settings
    llm_api_key: SecretStr
    llm_model_name: str
    llm_base_url: str
    
    embedding_model_name: str 
    max_tokens: int
    overlap: int
    
    vector_db_path: str
    collection_name: str
    space_type: str
    result_limit: int
    
    #Storage paths
    raw_data_dir: Path = Path("data/raw")
    parsed_data_dir: Path = Path("data/parsed")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()