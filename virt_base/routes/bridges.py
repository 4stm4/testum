from fastapi import HTTPException
from virt_base.application.models import VMInterface, BridgeNetwork



class BridgeAPI:

    def __init__(self, bridge_manager, router):
        self.bridge_manager = bridge_manager
        router.post("/create")(self._create_bridge_network)
        router.post("/start")(self._start_bridge_network)
        router.post("/stop")(self._stop_bridge_network)
        router.delete("/delete")(self._delete_bridge_network)
        router.post("/attach")(self._attach_interface)
        router.post("/deattach")(self._detach_interface)

    async def _create_bridge_network(self, bridge_network: BridgeNetwork):
        self.bridge_manager.create_bridge_network(
            bridge_network.name, 
            bridge_network.bridge_name,
            bridge_network.ip_address,
            bridge_network.netmask,
            bridge_network.dhcp_start,
            bridge_network.dhcp_end
        )
        return {"message": f"Bridge network {bridge_network.name} created successfully"}

    async def _start_bridge_network(self, name: str):
        self.bridge_manager.start_network(name)
        return {"message": f"Bridge network {name} started"}


    async def _stop_bridge_network(self, name: str):
        try:
            self.bridge_manager.stop_network(name)
            return {"message": f"Bridge network {name} stopped"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def _delete_bridge_network(self, name: str):
        try:
            self.bridge_manager.delete_network(name)
            return {"message": f"Bridge network {name} deleted"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def _attach_interface(self, vm_interface: VMInterface):
        try:
            self.bridge_manager.attach_interface(
                vm_interface.vm_name, 
                vm_interface.network_name, 
                vm_interface.mac_address, 
                vm_interface.model
            )
            return {"message": f"Interface attached to VM {vm_interface.vm_name} on network {vm_interface.network_name}"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def _detach_interface(self, vm_interface: VMInterface):
        try:
            self.bridge_manager.detach_interface(
                vm_interface.vm_name, 
                vm_interface.network_name, 
                vm_interface.mac_address, 
                vm_interface.model
            )
            return {"message": f"Interface detached from VM {vm_interface.vm_name} on network {vm_interface.network_name}"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
