from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, field_validator
from typing import List, Any, Union
import json

class Settings(BaseSettings):
    bot_token: SecretStr
    # We use Union to allow it to be a string or int temporarily so that the validator can handle it
    admin_ids: Any = []
    db_url: str = "sqlite+aiosqlite:///./barber.db"
    cashback_percent: int = 5
    max_bonus_payment_percent: int = 50
    referral_reward: int = 100

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: Any) -> List[int]:
        if isinstance(v, int):
            return [v]
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("[") and v.endswith("]"):
                return json.loads(v)
            return [int(i.strip()) for i in v.split(",") if i.strip()]
        if isinstance(v, list):
            return [int(i) for i in v]
        return v

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

settings = Settings()
