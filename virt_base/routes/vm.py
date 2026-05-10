from __future__ import annotations

from fastapi import HTTPException


class VMAPI:

    def __init__(self, vm_manager, router):
        self.vm_manager = vm_manager
        # router.post('/create')(self._create)
        # router.post('/delete')(self._delete)
        # router.post('/clone')(self._clone)
        router.post('/run')(self._run)
        router.post('/stop')(self._stop)
        router.post('/delete')(self._delete)
        router.post('/list_all')(self._list_all)

    async def _run(self, name: str):
        try:
            return self.vm_manager.run(name)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _stop(self, name: str):
        try:
            return self.vm_manager.stop(name)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _delete(self, name: str):
        try:
            return self.vm_manager.delete(name)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _list_all(self, filter: str):
        try:
            return self.vm_manager.list_all()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # async def _create(self, model: CreateVolumeModel):
    #     try:
    #         self.volume_manager.create(
    #             name=model.name,
    #             pool_name=model.pool_name,
    #             path=model.path,
    #             capacity=model.capacity,
    #         )
    #         return {"message": f"Volume {model.name} created successfully"}
    #     except Exception as e:
    #         raise HTTPException(status_code=500, detail=str(e))

    # async def _delete(self, name: str, pool_name: str):
    #     try:
    #         self.volume_manager.delete(
    #             pool_name=pool_name, name=name)
    #         return {"message": f"Volume {name} deleted successfully"}
    #     except Exception as e:
    #         raise HTTPException(status_code=500, detail=str(e))

    # async def _clone(self, model: CloneVolumeModel):
    #     try:
    #         self.volume_manager.clone(
    #             pool_name=model.pool_name, name=model.name, volume_name=model.volume_name)
    #         return {"message": f"Volume {model.volume_name} cloned to {model.name} successfully"}
    #     except Exception as e:
    #         raise HTTPException(status_code=500, detail=str(e))
