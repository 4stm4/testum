import xml.etree.ElementTree as ET

import libvirt


class NatManager:
    def __init__(self, uri):
        self.conn = libvirt.open(uri)
        if self.conn is None:
            raise Exception('Failed to open connection to {}'.format(uri))

    def create_nat_network(self, name, subnet, dhcp_start, dhcp_end):
        xml = f"""
        <network>
            <name>{name}</name>
            <forward mode='nat'/>
            <ip address='{subnet.split('/')[0]}' netmask='255.255.255.0'>
                <dhcp>
                    <range start='{dhcp_start}' end='{dhcp_end}'/>
                </dhcp>
            </ip>
        </network>
        """
        network = self.conn.networkDefineXML(xml)
        if network is None:
            raise Exception('Failed to define network from XML definition')
        network.create()
        network.setAutostart(True)

    def start_nat_network(self, name):
        network = self.conn.networkLookupByName(name)
        network.create()

    def stop_nat_network(self, name):
        network = self.conn.networkLookupByName(name)
        print(network)
        network.destroy()

    def delete_nat_network(self, name):
        network = self.conn.networkLookupByName(name)
        network.destroy()
        network.undefine()

    def attach_interface(self, vm_name, network_name):
        domain = self.conn.lookupByName(vm_name)
        network = self.conn.networkLookupByName(network_name)
        mac_address = self.generate_mac()

        interface_xml = f"""
        <interface type='network'>
            <mac address='{mac_address}'/>
            <source network='{network_name}'/>
            <model type='virtio'/>
        </interface>
        """

        domain.attachDeviceFlags(interface_xml, libvirt.VIR_DOMAIN_AFFECT_LIVE | libvirt.VIR_DOMAIN_AFFECT_CONFIG)

    def detach_interface(self, vm_name, network_name):
        domain = self.conn.lookupByName(vm_name)
        xml_desc = domain.XMLDesc()
        root = ET.fromstring(xml_desc)
        interface_element = None

        for interface in root.findall('devices/interface'):
            if interface.find('source').get('network') == network_name:
                interface_element = interface
                break

        if interface_element is None:
            raise Exception(f'No interface connected to network {network_name} found on VM {vm_name}')

        domain.detachDeviceFlags(ET.tostring(interface_element, encoding="unicode"), libvirt.VIR_DOMAIN_AFFECT_LIVE | libvirt.VIR_DOMAIN_AFFECT_CONFIG)

    def generate_mac(self):
        import random
        mac = [ 0x52, 0x54, 0x00,
                random.randint(0x00, 0xff),
                random.randint(0x00, 0xff),
                random.randint(0x00, 0xff) ]
        return ':'.join(map(lambda x: "%02x" % x, mac))

    def close_connection(self):
        self.conn.close()