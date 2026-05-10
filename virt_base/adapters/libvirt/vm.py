import libvirt
from .dto import Domain, VirDomainInfo, domain_state_list
from virt_base.application.generator2 import VMXMLGenerator
from virt_base.application.models import CPUUsageStats, HostInfo, VMConfig



class VMManager:

    def __init__(self, uri):
        self.conn = libvirt.open(uri)


    def list_all(self):
        vm = self.conn.listAllDomains()
        vm_list = []
        for machine in vm:
            try:
                machine_info = machine.info()
                domain_info = VirDomainInfo(
                    state=domain_state_list[machine_info[0]],
                    max_mem=machine_info[1],
                    memory=machine_info[2],
                    cpu_numb=machine_info[3],
                    cpu_time=machine_info[4]
                )

            except Exception as e:
                print(e)
            vm_list.append(
                Domain(
                    id=machine.ID(),
                    name=machine.name(),
                    uuid=machine.UUIDString(),
                    os_type=machine.OSType(),
                    autostart=machine.autostart(),
                    domain_info=domain_info,
                )
            )
        return vm_list

    def create_virtual_machine(self, config: VMConfig):
        # Generate the XML configuration
        generator = VMXMLGenerator(config)
        xml_string = generator.generate_xml()
        # Create the virtual machine
        try:
            # self.conn.createXML(xml_string, 0)
            self.conn.defineXML(xml_string)
        except libvirt.libvirtError as e:
            raise ValueError(f"Libvirt error: {e}")

    def get_host_resources(self) -> HostInfo:
        # Получаем информацию о хосте
        host_info = self.conn.getInfo()
        free_memory = self.conn.getFreeMemory() / 1024  # в килобайтах
        total_memory = host_info[2]  # в килобайтах
        # Получение информации о процессорах
        cpu_stats = self.conn.getCPUStats(
            cpuNum=-1, flags=0)  # -1 означает "все CPU"
        # Создание списка с использованием CPUUsageStats модели
        cpu_usage_stats = CPUUsageStats(
            kernel=cpu_stats['kernel'],
            user=cpu_stats['user'],
            idle=cpu_stats['idle'],
            iowait=cpu_stats['iowait']
        )
        return HostInfo(
            architecture=host_info[0],
            cpu_count=host_info[1],
            cpu_frequency=host_info[3],
            total_memory_kb=total_memory,
            free_memory_kb=free_memory,
            cpu_usage_stats=cpu_usage_stats
        )

    def run(self, vm_name: str):
        try:
            domain = self.conn.lookupByName(vm_name)
            if domain is None:
                return f'Failed to find the domain {vm_name}'

            if domain.isActive():
                print(f'The domain {vm_name} is already active')
            else:
                if domain.create() < 0:
                    return f'Failed to start the domain {vm_name}'
                else:
                    return f'The domain {vm_name} has been started'
        except libvirt.libvirtError as e:
            raise ValueError(f"Libvirt error: {e}")

    def stop(self, vm_name: str):
        try:
            domain = self.conn.lookupByName(vm_name)
            if domain is None:
                return f'Failed to find the domain {vm_name}'

            if not domain.isActive():
                return f'The domain {vm_name} is not active'
            else:
                if domain.shutdown() < 0:
                    return f'Failed to stop the domain {vm_name}'
                else:
                    return f'The domain {vm_name} is being stopped'
        except libvirt.libvirtError as e:
            raise ValueError(f"Libvirt error: {e}")

    def delete(self, vm_name: str):
            try:
                domain = self.conn.lookupByName(vm_name)
                if domain:
                    # Проверяем, запущена ли ВМ
                    if domain.isActive():
                        # Если ВМ активна, принудительно останавливаем ее
                        domain.destroy()
                    # domain.undefineFlags(libvirt.VIR_DOMAIN_UNDEFINE_MANAGED_SAVE)
                    return f'VM с именем {vm_name} успешно удалена.'
                else:
                    return f'VM с именем {vm_name} не найдена.'
            except libvirt.libvirtError as e:
                raise ValueError(f"Ошибка при удалении VM: {e}")
