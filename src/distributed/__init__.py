"""Distributed training components for genetic algorithm"""

from .server import DistributedServer
from .client import DistributedClient
from .protocol import WorkUnit, WorkResult

__all__ = ['DistributedServer', 'DistributedClient', 'WorkUnit', 'WorkResult']
