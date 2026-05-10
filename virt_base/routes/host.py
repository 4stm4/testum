from fastapi import HTTPException


class HostAPI:

    def __init__(self, host_manager, router):
        self.host_manager = host_manager
        router.get('/capabilities')(self._capabilities)


    async def _capabilities(self):
        try:
            capabilities = self.host_manager.get_capabilities()
            return capabilities
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
