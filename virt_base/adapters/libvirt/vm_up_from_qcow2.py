import libvirt

class VirtualMachineManager:
    def __init__(self, uri):
        self.uri = uri
        self.conn = libvirt.open(self.uri)
        if self.conn is None:
            raise Exception('Failed to open connection to hypervisor')

    def create_vm_from_image(self, image_path, vm_name, cpu_cnt, ram_cnt):
        try:
            # Define XML for the VM
            xml = f'''
            <domain type='qemu'>
                <name>{vm_name}</name>
                <memory unit='GB'>{ram_cnt}</memory>
                <vcpu placement='static'>{cpu_cnt}</vcpu>
                <os>
                    <type arch='x86_64' machine='pc-i440fx-2.1'>hvm</type>
                    <boot dev='hd'/>
                </os>
                <devices>
                    <disk type='file' device='disk'>
                        <driver name='qemu' type='qcow2'/>
                        <source file='{image_path}'/>
                        <target dev='vda' bus='virtio'/>
                    </disk>
                    <interface type='network'>
                        <source network='default'/>
                        <model type='virtio'/>
                    </interface>
                </devices>
            </domain>
            '''
            
            # Create the VM
            dom = self.conn.createXML(xml, 0)
            return dom
        except libvirt.libvirtError as e:
            print(f'Failed to create VM: {e}')
            return None