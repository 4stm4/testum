from fastapi import HTTPException


class InstallerAPI:

    def __init__(self, installer_manager, router):
        self.installer_manager = installer_manager
        router.post('/qemu_libvirt')(self._qemu_libvirt)
        router.post('/firewall')(self._firewall)

    async def _qemu_libvirt(self):
        return self.installer_manager.qemu_libvirt()

    async def _firewall(self):
        return self.installer_manager.firewall()
