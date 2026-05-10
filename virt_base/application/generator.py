import xml.etree.ElementTree as ET
from xml.dom import minidom

from virt_base.application.models import VMConfig


class VMXMLGenerator:
    def __init__(self, config: VMConfig):
        self.config = config

    def generate_xml(self) -> str:
        domain = ET.Element('domain', type='qemu')
        
        name = ET.SubElement(domain, 'name')
        name.text = self.config.name

        memory = ET.SubElement(domain, 'memory', unit='MiB')
        memory.text = str(self.config.memory)
        
        vcpu = ET.SubElement(domain, 'vcpu', placement='static')
        vcpu.text = str(self.config.vcpu)

        os = ET.SubElement(domain, 'os')
        os_type = ET.SubElement(os, 'type', arch='x86_64', machine='pc-i440fx-2.9')
        os_type.text = 'hvm'

        boot_hd = ET.SubElement(os, 'boot', dev='hd')
        boot_cdrom = ET.SubElement(os, 'boot', dev='cdrom')

        devices = ET.SubElement(domain, 'devices')

        # Disk
        disk = ET.SubElement(devices, 'disk', type='file', device='disk')
        disk_driver = ET.SubElement(disk, 'driver', name='qemu', type='qcow2')
        disk_source = ET.SubElement(disk, 'source', file=self.config.disk_path)
        disk_target = ET.SubElement(disk, 'target', dev='vda', bus='virtio')
        disk_address = ET.SubElement(disk, 'address', type='pci', domain='0x0000', bus='0x00', slot='0x04', function='0x0')

        # CDROM
        cdrom = ET.SubElement(devices, 'disk', type='file', device='cdrom')
        cdrom_driver = ET.SubElement(cdrom, 'driver', name='qemu', type='raw')
        cdrom_source = ET.SubElement(cdrom, 'source', file=self.config.cdrom_iso_path)
        cdrom_target = ET.SubElement(cdrom, 'target', dev='hda', bus='ide')
        cdrom_readonly = ET.SubElement(cdrom, 'readonly')
        # cdrom_address = ET.SubElement(cdrom, 'address', type='pci', domain='0x0000', bus='0x01', slot='0x01', function='0x0')

        # Network Interface
        interface = ET.SubElement(devices, 'interface', type='bridge')
        mac = ET.SubElement(interface, 'mac', address=self.config.mac_address)
        source = ET.SubElement(interface, 'source', bridge=self.config.bridge)
        model = ET.SubElement(interface, 'model', type='virtio')
        address = ET.SubElement(interface, 'address', type='pci', domain='0x0000', bus='0x00', slot='0x03', function='0x0')

        # Other devices
        serial = ET.SubElement(devices, 'serial', type='pty')
        serial_target = ET.SubElement(serial, 'target', port='0')

        console = ET.SubElement(devices, 'console', type='pty')
        console_target = ET.SubElement(console, 'target', type='serial', port='0')

        input_tablet = ET.SubElement(devices, 'input', type='tablet', bus='usb')
        input_mouse = ET.SubElement(devices, 'input', type='mouse', bus='ps2')

        graphics = ET.SubElement(devices, 'graphics', type='vnc', port='-1')
        
        video = ET.SubElement(devices, 'video')
        model = ET.SubElement(video, 'model', type='cirrus', vram='16384', heads='1')
        address = ET.SubElement(video, 'address', type='pci', domain='0x0000', bus='0x00', slot='0x02', function='0x0')

        memballoon = ET.SubElement(devices, 'memballoon', model='virtio')
        address = ET.SubElement(memballoon, 'address', type='pci', domain='0x0000', bus='0x00', slot='0x05', function='0x0')

        seclabel = ET.SubElement(domain, 'seclabel', type='dynamic', model='dac', relabel='yes')

        # Return pretty-printed XML string
        return self._prettify(domain)

    def _prettify(self, elem):
        rough_string = ET.tostring(elem, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")
