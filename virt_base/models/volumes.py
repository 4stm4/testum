from pydantic import BaseModel
from typing import Optional


class CreateVolumeModel(BaseModel):
    name: str
    pool_name: str
    path: str
    capacity: int

class CloneVolumeModel(BaseModel):
    name: str
    pool_name: str
    volume_name: str