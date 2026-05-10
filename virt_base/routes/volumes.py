from __future__ import annotations

from fastapi import HTTPException
from virt_base.models.volumes import CreateVolumeModel, CloneVolumeModel


class VolumeAPI:

    def __init__(self, volume_manager, router):
        self.volume_manager = volume_manager
        router.post('/create')(self._create)
        router.post('/delete')(self._delete)
        router.post('/clone')(self._clone)
        router.post('/list_all')(self._list_all)

    async def _create(self, model: CreateVolumeModel):
        try:
            self.volume_manager.create(
                name=model.name,
                pool_name=model.pool_name,
                path=model.path,
                capacity=model.capacity,
            )
            return {"message": f"Volume {model.name} created successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _delete(self, name: str, pool_name: str):
        try:
            self.volume_manager.delete(
                pool_name=pool_name, name=name)
            return {"message": f"Volume {name} deleted successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _clone(self, model: CloneVolumeModel):
        try:
            self.volume_manager.clone(
                pool_name=model.pool_name, name=model.name, volume_name=model.volume_name)
            return {"message": f"Volume {model.volume_name} cloned to {model.name} successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _list_all(self, pool_name):
        try:
            return self.volume_manager.list_all(pool_name)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))