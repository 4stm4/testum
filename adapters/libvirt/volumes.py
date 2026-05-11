'''
примеры создания volumes https://libvirt-python.readthedocs.io/storage-pools/#creating-and-deleting-volumes
'''
from __future__ import annotations
import libvirt

from .xml import XML
from .dto import Volume


class VolumesManager:

    def __init__(self, uri: str):
        self.conn = libvirt.open(uri)

    def create(self, pool_name: str, name: str, path: str, capacity: int):
        pool = self.conn.storagePoolLookupByName(pool_name)
        xml_desc = self._generate_xml(
            name, path, capacity)
        return pool.createXML(xml_desc, 0)

    def delete(self, name: str, pool_name: str) -> None:
        pool = self.conn.storagePoolLookupByName(pool_name)
        volume = pool.storageVolLookupByName(name)
        volume.wipe()
        volume.delete()

    # FIXME: В процессе
    def clone(self, name: str, pool_name: str, volume_name: str):
        pool = self.conn.storagePoolLookupByName(pool_name)
        target_volume = pool.storageVolLookupByName(volume_name)
        pool.createXMLFrom()
        pass

    def list_all(self, pool_name: str) -> list[any]:
        pool = self.conn.storagePoolLookupByName(pool_name)
        if not pool:
            raise SystemExit("Failed to find storage pool " + pool_name)

        volumes = pool.listVolumes()
        volumes_list = []
        for volume_name in volumes:
            volume = pool.storageVolLookupByName(volume_name)
            info = volume.info()
            volumes_list.append(
                Volume(
                    name=volume_name,
                    type=info[0],
                    capacity=round(info[1]/1024/1024/1024, 2),
                    allocation=round(info[2]/1024/1024/1024, 2)
                )
            )
        return volumes_list

    @staticmethod
    def _generate_xml(name: str, path: str, capacity: int) -> str:
        xml_trgt_path = XML('path', path).full_tag()
        xml_owner = XML('owner', 1000).full_tag()
        xml_group = XML('group', 1000).full_tag()
        xml_mode = XML('mode', '0777').full_tag()
        xml_label = XML('label', name).full_tag()
        xml_format = XML('format', '').half_tag(type='qcow2')
        xml_permissions = XML('permissions', xml_owner +
                              xml_group + xml_mode + xml_label).full_tag()
        xml_target = XML('target', xml_trgt_path +
                         xml_permissions + xml_format).full_tag()
        xml_name = XML('name', name).full_tag()
        xml_allocation = XML('allocation', 0).full_tag()
        xml_capacity = XML('capacity', capacity).full_tag(unit='G')
        volume_xml = XML('volume', xml_name + xml_allocation +
                         xml_capacity + xml_target).full_tag()
        return volume_xml
