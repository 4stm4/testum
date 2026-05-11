'''
примеры создания пулов https://libvirt.org/storage.html#example-directory-pool-input-definition
'''
import libvirt

from .dto import Pool
from .xml import XML
from pydantic import BaseModel


class Host(BaseModel):
  uuid: str
  arch: str
  cpus: str
  memory: int
  pages: str
  iommu: str


class HostManager:

    def __init__(self, uri):
        self.conn = libvirt.open(uri)

    @staticmethod
    def _get_capabilities_data(data: str):
        n = 0
        lines = data.split('\n')
        host_dict = {}
        for line in lines:
            if n and line.find('</host>') > 0:
                n = 0
            if n > 0:
                # разделяем структуру host
                all_words = line.replace('<', ' ').replace('>', ' ').split(' ')
                words = []
                for word in all_words:
                    if word == '' or word.startswith('/'):
                        continue
                    words.append(word)
                if len(words) == 2:
                    host_dict[words[0]] = words[1]
                if len(words) == 3:
                    host_dict[words[0]] = words[2]
            if not n and line.find('<host>') > 0:
                n = 1
        return host_dict


    def get_capabilities(self):
        caps = self.conn.getCapabilities()
        return self._get_capabilities_data(caps)
