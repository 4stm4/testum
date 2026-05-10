class FirewallAPI:

    def __init__(self, firewall_manager, router):
        self.firewall_manager = firewall_manager
        router.post('/status')(self._status)

    async def _status(self):
        return self.firewall_manager.status()
