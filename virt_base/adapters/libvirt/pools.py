'''
примеры создания пулов https://libvirt.org/storage.html#example-directory-pool-input-definition
'''
from __future__ import annotations
from enum import Enum
import libvirt

from .dto import Pool
from .xml import XML


class PoolState(Enum):
    INACTIVE = 1
    ACTIVE = 2
    PERSISTENT = 4
    TRANSIENT = 8
    AUTOSTART = 16
    NO_AUTOSTART = 32
    DIR = 64
    FS = 128
    NETFS = 256
    LOGICAL = 512
    DISK = 1024
    ISCSI = 2048
    SCSI = 4096
    MPATH = 8192
    RBD = 16384
    SHEEPDOG = 32768
    GLUSTER = 65536
    ZFS = 131072
    VSTORAGE = 262144
    ISCSI_DIRECT = 524288


class StoragePoolManager:

    def __init__(self, uri):
        try:
            self.conn = libvirt.open(uri)
        except Exception as error:
            print(error)

    def create(self, name: str, pool_type, source=None, target=None, host=None):
        xml_desc = self._generate_xml(
            name, pool_type, source, target, host)
        return self.conn.storagePoolDefineXML(xml_desc, 0)

    def delete(self, name: str) -> None:
        pool = self.conn.storagePoolLookupByName(name)
        pool.undefine()
        pool.delete()

    def activate(self, name: str) -> None:
        pool = self.conn.storagePoolLookupByName(name)
        pool.create()

    def deactivate(self, name: str) -> None:
        pool = self.conn.storagePoolLookupByName(name)
        pool.destroy()

    def configure(self, name: str, autostart: bool):
        pool = self.conn.storagePoolLookupByName(name)
        if autostart:
            pool.setAutostart(1)
        if not autostart and pool.autostart:
            pool.setAutostart(0)

    def list_all(self, states: list[int]) -> list[Pool]:
        flags = sum(states)
        pools = self.conn.listAllStoragePools(flags=flags)
        pools_list = []
        for pool in pools:
            info = pool.info()
            num_of_volumes = 0 if not pool.isActive() else pool.numOfVolumes()
            pools_list.append(Pool(
                name=pool.name(),
                uuid=pool.UUIDString(),
                auto_start=bool(pool.autostart()),
                is_active=bool(pool.isActive()),
                is_persistent=bool(pool.isPersistent()),
                num_volumes=num_of_volumes,
                pool_state=info[0],
                capacity=info[1],
                allocation=info[2],
                available=info[3]
            ))
        return pools_list

    def monitor_usage(self, name: str) -> dict[str, any]:
        pool = self.conn.storagePoolLookupByName(name)
        pool.refresh()
        info = pool.info()
        return {
            "state": info[0],
            "capacity": info[1],
            "allocation": info[2],
            "available": info[3]
        }

    @staticmethod
    def _generate_xml(name: str, pool_type: str, source='', target='', host='') -> str:
        xml_trgt_path = XML('path', target).full_tag()
        xml_target = XML('target', xml_trgt_path).full_tag()
        xml_name = XML('name', name).full_tag()
        # for netfs, iSCSI
        xml_host = XML('host', '').half_tag(name=host)
        xml_dir = XML('dir', '').half_tag(path=source)
        xml_source_netfs = XML('source', xml_dir + xml_host).full_tag()
        # for dir, fs, disk
        xml_device = XML('device', '').half_tag(path=source)
        xml_source_device = XML('source', xml_device).full_tag()
        # for scsi
        xml_adapter = XML('adapter', '').half_tag(name=source)
        xml_source_adapter = XML('source', xml_adapter).full_tag()
        # for sheepdog https://github.com/sheepdog/sheepdog
        xml_source_host = XML('source', xml_name + xml_host).full_tag()
        # for gluster https://docs.gluster.org/en/v3/Administrator%20Guide/GlusterFS%20Introduction/
        xml_source_gluster = XML(
            'source', xml_name + xml_host + xml_dir).full_tag()
        # for zfs, logical https://zfsonlinux.org/

        # for vstorage https://wiki.openvz.org/Virtuozzo_Storage
        xml_source_name = XML('source', xml_name).full_tag()
        pools_values = {
            'dir': xml_source_device + xml_target,
            'fs': xml_source_device + xml_target,
            'netfs': xml_source_netfs + xml_target,
            'logical': '',
            'disk': xml_source_device + xml_target,
            'iscsi': xml_source_netfs + xml_target,
            'scsi': xml_source_adapter + xml_target,
            'mpath': '',
            'sheepdog': xml_source_host,
            'gluster': xml_source_gluster,
            'xfs': '',
            'vstorage': xml_source_name,
        }
        pool_xml = XML('pool', xml_name +
                       pools_values.get(pool_type, '')).full_tag(type=pool_type)
        return pool_xml
