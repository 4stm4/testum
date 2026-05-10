from __future__ import annotations

from fastapi import HTTPException
from virt_base.models.pools import CreatePoolModel, PoolUsageModel


class PoolAPI:

    def __init__(self, pool_manager, router):
        self.pool_manager = pool_manager
        router.post('/create')(self._create)
        router.delete('/delete')(self._delete)
        router.post('/activate')(self._activate)
        router.post('/deactivate')(self._deactivate)
        router.post('/configure')(self._configure)
        router.get('/monitor', response_model=PoolUsageModel)(self._monitor_usage)
        router.post('/list_all')(self._list_all)

    async def _create(self, model: CreatePoolModel):
        try:
            self.pool_manager.create(
                name=model.name,
                pool_type=model.pool_type,
                source=model.source,
                target=model.target,
                host=model.host,
            )
            return {"message": f"Pool {model.name} created successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _delete(self, name: str):
        try:
            self.pool_manager.delete(name)
            return {"message": f"Pool {name} deleted successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _activate(self, name: str):
        try:
            self.pool_manager.activate(name)
            return {"message": f"Pool {name} activated successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _deactivate(self, name: str):
        try:
            self.pool_manager.deactivate(name)
            return {"message": f"Pool {name} deactivated successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _monitor_usage(self, name: str):
        try:
            usage = self.pool_manager.monitor_usage(name)
            return usage
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _list_all(self, body_dict: dict[str, list[int]]):
        try:
            return self.pool_manager.list_all(body_dict['pool_state'])
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _configure(self, name: str, autostart: bool):
        try:
            self.pool_manager.configure(name, autostart)
            return {"message": f"Pool {name} configurated successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))