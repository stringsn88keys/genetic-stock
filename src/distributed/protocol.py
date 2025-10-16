"""Protocol definitions for distributed training"""

import pickle
import json
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
from enum import Enum


class MessageType(Enum):
    """Message types for client-server communication"""
    REGISTER = "register"
    WORK_REQUEST = "work_request"
    WORK_ASSIGNED = "work_assigned"
    WORK_RESULT = "work_result"
    NO_WORK = "no_work"
    HEARTBEAT = "heartbeat"
    SHUTDOWN = "shutdown"
    ERROR = "error"


@dataclass
class WorkerInfo:
    """Information about a worker client"""
    worker_id: str
    hostname: str
    platform: str
    cpu_count: int
    gpu_available: bool
    gpu_count: int
    gpu_names: list


@dataclass
class WorkUnit:
    """Unit of work to be distributed"""
    work_id: str
    work_type: str  # 'fitness_eval', 'backtest', etc.
    chromosome_data: Dict[str, Any]
    train_data_info: Dict[str, Any]
    config: Dict[str, Any]
    generation: int


@dataclass
class WorkResult:
    """Result of completed work"""
    work_id: str
    worker_id: str
    success: bool
    fitness_score: Optional[float] = None
    metrics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None


class Message:
    """Network message with type and payload"""

    def __init__(self, msg_type: MessageType, payload: Any = None):
        self.type = msg_type
        self.payload = payload

    def serialize(self) -> bytes:
        """Serialize message to bytes"""
        data = {
            'type': self.type.value,
            'payload': self.payload
        }
        return pickle.dumps(data)

    @staticmethod
    def deserialize(data: bytes) -> 'Message':
        """Deserialize message from bytes"""
        obj = pickle.loads(data)
        msg_type = MessageType(obj['type'])
        return Message(msg_type, obj['payload'])

    def __repr__(self):
        return f"Message(type={self.type.value}, payload_type={type(self.payload).__name__})"


def send_message(socket, message: Message):
    """Send a message over a socket with length prefix"""
    data = message.serialize()
    length = len(data).to_bytes(4, byteorder='big')
    socket.sendall(length + data)


def receive_message(socket) -> Optional[Message]:
    """Receive a message from a socket"""
    # Read length prefix
    length_data = receive_exact(socket, 4)
    if not length_data:
        return None

    length = int.from_bytes(length_data, byteorder='big')

    # Read message data
    data = receive_exact(socket, length)
    if not data:
        return None

    return Message.deserialize(data)


def receive_exact(socket, n: int) -> Optional[bytes]:
    """Receive exactly n bytes from socket"""
    data = bytearray()
    while len(data) < n:
        packet = socket.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return bytes(data)
