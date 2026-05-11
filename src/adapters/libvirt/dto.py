from dataclasses import dataclass
from enum import Enum


@dataclass
class Pool:
    name: str
    uuid: str
    auto_start: bool
    is_active: bool
    is_persistent: bool
    num_volumes: int
    pool_state: int
    capacity: int
    allocation: int
    available: int


@dataclass
class Volume:
    name: str
    type: int
    capacity: int
    allocation: int


@dataclass
class VirDomainInfo:
    state: str = ''  # unsigned char	state	the running state, one of virDomainState
    max_mem: int = 0  # unsigned long	maxMem	the maximum memory in KBytes allowed
    memory: int = 0  # unsigned long	memory	the memory in KBytes used by the domain
    cpu_numb: int = 0  # unsigned short	nrVirtCpu	the number of virtual CPUs for the domain
    cpu_time: int = 0  # unsigned long long	cpuTime	the CPU time used in nanoseconds


@dataclass
class Domain:
    id: str
    name: str
    uuid: str
    os_type: str
    autostart: str
    domain_info: VirDomainInfo


class DomainState(Enum):
    VIR_DOMAIN_NOSTATE = 0  # no state
    VIR_DOMAIN_RUNNING = 1  # the domain is running
    VIR_DOMAIN_BLOCKED = 2  # the domain is blocked on resource
    VIR_DOMAIN_PAUSED = 3  # the domain is paused by user
    VIR_DOMAIN_SHUTDOWN = 4  # the domain is being shut down
    VIR_DOMAIN_SHUTOFF = 5  # the domain is shut off
    VIR_DOMAIN_CRASHED = 6  # the domain is crashed
    VIR_DOMAIN_PMSUSPENDED = 7  # the domain is suspended by guest power management
    # NB: this enum value will increase over time as new states are added to the libvirt API. It reflects the last state supported by this version of the libvirt API.
    VIR_DOMAIN_LAST = 8


domain_state_list = ['No state',
                     'Running',
                     'Blocked',
                     'Paused',
                     'SHUTDOWN',
                     'SHUTOFF',
                     'CRASHED',
                     'PMSUSPENDED',
                     'LAST'
                     ]
