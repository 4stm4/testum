from pydantic import BaseModel


class NatNetwork(BaseModel):
    name: str
    subnet: str
    dhcp_start: str
    dhcp_end: str


class AttachDetachParams(BaseModel):
    vm_name: str
    network_name: str


# BridgeNetwork: содержит параметры для создания сети типа Bridge.
class BridgeNetwork(BaseModel):
    name: str
    bridge_name: str = 'virbr0'
    ip_address: str = '192.168.122.1'
    netmask: str = '255.255.255.0'
    dhcp_start: str = '192.168.122.100'
    dhcp_end: str = '192.168.122.254'


# VMInterface: содержит параметры для привязки/отвязки интерфейса виртуальной машины.
class VMInterface(BaseModel):
    vm_name: str
    network_name: str
    mac_address: str = '52:54:00:6b:3c:58'
    model: str = 'virtio'
