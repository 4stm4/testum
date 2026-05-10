import random
from typing import Optional

from pydantic import BaseModel, Field, constr


class VMConfig(BaseModel):
    name: constr(strict=True, min_length=1)
    memory: int = Field(..., gt=0)
    vcpu: int = Field(..., gt=0)
    disk_size: int = Field(..., gt=0)
    # FIXME: переосмыслить
    disk_path: str = Field(..., min_length=5) # полный путь и имя файла
    cdrom_iso_path: constr(strict=True, min_length=1)
    bridge: constr(strict=True, min_length=1)
    mac_address: Optional[constr(strict=True, pattern=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")]

    @staticmethod
    def generate_mac_address():
    #     return ":".join(f"{random.randint(0, 255):02x}" for _ in range(6))
    # def generate_mac_address():
        mac = [0x52, 0x54, 0x00,
            random.randint(0x00, 0x7F),  # 4-й октет
            random.randint(0x00, 0xFF),  # 5-й октет
            random.randint(0x00, 0xFF)]  # 6-й октет
        return ':'.join(map(lambda x: f"{x:02x}", mac))

    @classmethod
    def validate(cls, values):
        if 'mac_address' not in values or not values['mac_address']:
            values['mac_address'] = cls.generate_mac_address()
        return values


class CPUUsageStats(BaseModel):
    kernel: int
    user: int
    idle: int
    iowait: int


class HostInfo(BaseModel):
    architecture: str
    cpu_count: int
    cpu_frequency: int
    total_memory_kb: int
    free_memory_kb: int
    cpu_usage_stats: CPUUsageStats


class Permissions(BaseModel):
    mode: str
    owner: int
    group: int


class Target(BaseModel):
    path: str
    permissions: Permissions

