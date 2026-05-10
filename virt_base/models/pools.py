from pydantic import BaseModel
from typing import Optional


class CreatePoolModel(BaseModel):
    name: str
    pool_type: str
    source: Optional[str]
    target: Optional[str]
    host: Optional[str]


class AddResourceToPoolModel(BaseModel):
    pool_name: str
    resource: str


class PoolUsageModel(BaseModel):
    state: str
    capacity: int
    allocation: int
    available: int
