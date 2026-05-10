import sys

import libvirt


class BridgeManager:
    def __init__(self, uri):
        self.uri = uri
        self.conn = None

    def connect(self):
        try:
            self.conn = libvirt.open(self.uri)
            if self.conn is None:
                raise libvirt.libvirtError(f'Failed to open connection to {self.uri}')
            print(f'Connected to {self.uri}')
        except libvirt.libvirtError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)

    def disconnect(self):
        if self.conn:
            self.conn.close()
            print(f'Disconnected from {self.uri}')

    def create_bridge_network(self, name, bridge_name='virbr0', ip_address='192.168.122.1', netmask='255.255.255.0', dhcp_start='192.168.122.100', dhcp_end='192.168.122.254'):
        bridge_xml = f"""
        <network>
            <name>{name}</name>
            <bridge name='{bridge_name}'/>
            <forward mode='bridge'/>
            <ip address='{ip_address}' netmask='{netmask}'>
                <dhcp>
                    <range start='{dhcp_start}' end='{dhcp_end}'/>
                </dhcp>
            </ip>
        </network>
        """
        try:
            network = self.conn.networkCreateXML(bridge_xml)
            print(f'Network {name} created successfully.')
            return network
        except libvirt.libvirtError as e:
            print(f'Failed to create network: {e}', file=sys.stderr)

    def get_network(self, name):
        try:
            network = self.conn.networkLookupByName(name)
            print(f'Network {network.name()} found.')
            return network
        except libvirt.libvirtError as e:
            print(f'Failed to lookup network: {e}', file=sys.stderr)

    def start_network(self, name):
        network = self.get_network(name)
        if network:
            try:
                network.create()
                print(f'Network {network.name()} has been started.')
            except libvirt.libvirtError as e:
                print(f'Failed to start network: {e}', file=sys.stderr)

    def stop_network(self, name):
        network = self.get_network(name)
        if network:
            try:
                network.destroy()
                print(f'Network {network.name()} has been stopped.')
            except libvirt.libvirtError as e:
                print(f'Failed to stop network: {e}', file=sys.stderr)

    def delete_network(self, name):
        network = self.get_network(name)
        if network:
            try:
                network.undefine()
                print(f'Network {network.name()} has been deleted.')
            except libvirt.libvirtError as e:
                print(f'Failed to undefine network: {e}', file=sys.stderr)

    def attach_interface(self, vm_name, network_name, mac_address='52:54:00:6b:3c:58', model='virtio'):
        dom = self.conn.lookupByName(vm_name)
        iface_xml = f"""
        <interface type='network'>
            <mac address='{mac_address}'/>
            <source network='{network_name}'/>
            <model type='{model}'/>
        </interface>
        """
        try:
            dom.attachDevice(iface_xml)
            print(f'Interface attached to VM {vm_name} on network {network_name}')
        except libvirt.libvirtError as e:
            print(f'Failed to attach interface: {e}', file=sys.stderr)

    def detach_interface(self, vm_name, network_name, mac_address='52:54:00:6b:3c:58', model='virtio'):
        dom = self.conn.lookupByName(vm_name)
        iface_xml = f"""
        <interface type='network'>
            <mac address='{mac_address}'/>
            <source network='{network_name}'/>
            <model type='{model}'/>
        </interface>
        """
        try:
            dom.detachDevice(iface_xml)
            print(f'Interface detached from VM {vm_name} on network {network_name}')
        except libvirt.libvirtError as e:
            print(f'Failed to detach interface: {e}', file=sys.stderr)


# Пример использования
if __name__ == '__main__':
    uri = 'qemu:///system'
    bridge_manager = BridgeManager(uri)

    bridge_manager.connect()

    # Создание сети Bridge
    bridge_manager.create_bridge_network('bridge_network_name')

    # Запуск сети
    bridge_manager.start_network('bridge_network_name')

    # Остановка сети
    bridge_manager.stop_network('bridge_network_name')

    # Удаление сети
    bridge_manager.delete_network('bridge_network_name')

    # Привязка интерфейса к ВМ
    bridge_manager.attach_interface('vm_name', 'bridge_network_name')

    # Отвязка интерфейса от ВМ
    bridge_manager.detach_interface('vm_name', 'bridge_network_name')

    bridge_manager.disconnect()
