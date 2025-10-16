"""Distributed training server for workload distribution"""

import socket
import threading
import logging
import time
import queue
from typing import Dict, List, Optional, Callable
from datetime import datetime
import uuid

from .protocol import (
    Message, MessageType, WorkUnit, WorkResult, WorkerInfo,
    send_message, receive_message
)

logger = logging.getLogger(__name__)


class WorkerConnection:
    """Represents a connected worker"""

    def __init__(self, worker_id: str, conn: socket.socket, addr: tuple, info: WorkerInfo):
        self.worker_id = worker_id
        self.conn = conn
        self.addr = addr
        self.info = info
        self.last_heartbeat = time.time()
        self.assigned_work = []  # List of work_ids
        self.completed_count = 0
        self.lock = threading.Lock()

    def is_alive(self, timeout: float = 30.0) -> bool:
        """Check if worker is still alive"""
        return (time.time() - self.last_heartbeat) < timeout

    def update_heartbeat(self):
        """Update last heartbeat time"""
        self.last_heartbeat = time.time()


class DistributedServer:
    """Server for distributing training workload across multiple machines"""

    def __init__(self, host: str = '0.0.0.0', port: int = 9999):
        """
        Initialize distributed training server

        Args:
            host: Host address to bind to (0.0.0.0 for all interfaces)
            port: Port to listen on
        """
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False

        # Worker management
        self.workers: Dict[str, WorkerConnection] = {}
        self.workers_lock = threading.Lock()

        # Work queue management
        self.work_queue = queue.Queue()
        self.pending_work: Dict[str, WorkUnit] = {}
        self.completed_work: Dict[str, WorkResult] = {}
        self.work_lock = threading.Lock()

        # Callback for completed work
        self.result_callback: Optional[Callable[[WorkResult], None]] = None

        # Statistics
        self.stats = {
            'workers_registered': 0,
            'work_units_submitted': 0,
            'work_units_completed': 0,
            'work_units_failed': 0,
            'total_execution_time': 0.0
        }

    def start(self):
        """Start the server"""
        logger.info(f"Starting distributed training server on {self.host}:{self.port}")

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(10)
        self.server_socket.settimeout(1.0)  # Timeout for checking running flag

        self.running = True

        # Start accept thread
        accept_thread = threading.Thread(target=self._accept_connections, daemon=True)
        accept_thread.start()

        # Start monitoring thread
        monitor_thread = threading.Thread(target=self._monitor_workers, daemon=True)
        monitor_thread.start()

        logger.info("Server started successfully")

    def stop(self):
        """Stop the server"""
        logger.info("Stopping distributed training server")
        self.running = False

        # Send shutdown to all workers
        with self.workers_lock:
            for worker in self.workers.values():
                try:
                    send_message(worker.conn, Message(MessageType.SHUTDOWN))
                    worker.conn.close()
                except:
                    pass

        if self.server_socket:
            self.server_socket.close()

        logger.info("Server stopped")

    def submit_work(self, work_unit: WorkUnit):
        """Submit a work unit for processing"""
        with self.work_lock:
            self.pending_work[work_unit.work_id] = work_unit
            self.work_queue.put(work_unit)
            self.stats['work_units_submitted'] += 1

    def submit_work_batch(self, work_units: List[WorkUnit]):
        """Submit multiple work units at once"""
        with self.work_lock:
            for work_unit in work_units:
                self.pending_work[work_unit.work_id] = work_unit
                self.work_queue.put(work_unit)
            self.stats['work_units_submitted'] += len(work_units)

    def get_results(self, timeout: Optional[float] = None) -> List[WorkResult]:
        """Get all completed results"""
        with self.work_lock:
            results = list(self.completed_work.values())
            self.completed_work.clear()
            return results

    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for all pending work to complete

        Returns:
            True if all work completed, False if timeout
        """
        start_time = time.time()

        while self.running:
            with self.work_lock:
                pending_count = len(self.pending_work)
                queue_size = self.work_queue.qsize()

                if pending_count == 0 and queue_size == 0:
                    return True

            if timeout and (time.time() - start_time) > timeout:
                return False

            time.sleep(0.5)

        return False

    def set_result_callback(self, callback: Callable[[WorkResult], None]):
        """Set callback function for when work is completed"""
        self.result_callback = callback

    def get_statistics(self) -> Dict:
        """Get server statistics"""
        with self.workers_lock:
            active_workers = sum(1 for w in self.workers.values() if w.is_alive())

        return {
            **self.stats,
            'active_workers': active_workers,
            'total_workers': len(self.workers),
            'pending_work': len(self.pending_work),
            'queue_size': self.work_queue.qsize()
        }

    def _accept_connections(self):
        """Accept incoming worker connections"""
        while self.running:
            try:
                conn, addr = self.server_socket.accept()
                logger.info(f"New connection from {addr}")

                # Handle in separate thread
                thread = threading.Thread(
                    target=self._handle_worker,
                    args=(conn, addr),
                    daemon=True
                )
                thread.start()

            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"Error accepting connection: {e}")

    def _handle_worker(self, conn: socket.socket, addr: tuple):
        """Handle communication with a worker"""
        worker_id = None

        try:
            conn.settimeout(5.0)

            # Wait for registration
            msg = receive_message(conn)
            if not msg or msg.type != MessageType.REGISTER:
                logger.warning(f"Invalid registration from {addr}")
                conn.close()
                return

            # Process registration
            worker_info = msg.payload
            worker_id = str(uuid.uuid4())

            worker = WorkerConnection(worker_id, conn, addr, worker_info)

            with self.workers_lock:
                self.workers[worker_id] = worker
                self.stats['workers_registered'] += 1

            logger.info(f"Worker registered: {worker_id} ({worker_info['hostname']}) "
                       f"- CPUs: {worker_info['cpu_count']}, "
                       f"GPUs: {worker_info['gpu_count']}")

            # Send acknowledgment
            send_message(conn, Message(MessageType.REGISTER, {'worker_id': worker_id}))

            # Handle worker requests
            conn.settimeout(None)
            while self.running:
                msg = receive_message(conn)
                if not msg:
                    break

                if msg.type == MessageType.WORK_REQUEST:
                    self._handle_work_request(worker)

                elif msg.type == MessageType.WORK_RESULT:
                    self._handle_work_result(worker, msg.payload)

                elif msg.type == MessageType.HEARTBEAT:
                    worker.update_heartbeat()

        except Exception as e:
            logger.error(f"Error handling worker {worker_id}: {e}")

        finally:
            # Clean up worker
            if worker_id:
                with self.workers_lock:
                    if worker_id in self.workers:
                        worker = self.workers[worker_id]
                        # Re-queue any assigned work
                        with self.work_lock:
                            for work_id in worker.assigned_work:
                                if work_id in self.pending_work:
                                    self.work_queue.put(self.pending_work[work_id])
                        del self.workers[worker_id]
                        logger.info(f"Worker disconnected: {worker_id}")

            try:
                conn.close()
            except:
                pass

    def _handle_work_request(self, worker: WorkerConnection):
        """Handle work request from worker"""
        try:
            # Get work from queue (non-blocking)
            work_unit = self.work_queue.get_nowait()

            with worker.lock:
                worker.assigned_work.append(work_unit.work_id)

            # Send work to worker
            send_message(worker.conn, Message(MessageType.WORK_ASSIGNED, work_unit))
            logger.debug(f"Assigned work {work_unit.work_id} to worker {worker.worker_id}")

        except queue.Empty:
            # No work available
            send_message(worker.conn, Message(MessageType.NO_WORK))

    def _handle_work_result(self, worker: WorkerConnection, result: WorkResult):
        """Handle work result from worker"""
        logger.debug(f"Received result for work {result.work_id} from worker {worker.worker_id}")

        with worker.lock:
            if result.work_id in worker.assigned_work:
                worker.assigned_work.remove(result.work_id)
            worker.completed_count += 1

        with self.work_lock:
            # Remove from pending
            if result.work_id in self.pending_work:
                del self.pending_work[result.work_id]

            # Add to completed
            self.completed_work[result.work_id] = result

            # Update stats
            if result.success:
                self.stats['work_units_completed'] += 1
                if result.execution_time:
                    self.stats['total_execution_time'] += result.execution_time
            else:
                self.stats['work_units_failed'] += 1

        # Call callback if set
        if self.result_callback:
            try:
                self.result_callback(result)
            except Exception as e:
                logger.error(f"Error in result callback: {e}")

    def _monitor_workers(self):
        """Monitor worker health and remove dead workers"""
        while self.running:
            time.sleep(10)

            with self.workers_lock:
                dead_workers = [
                    wid for wid, worker in self.workers.items()
                    if not worker.is_alive()
                ]

                for wid in dead_workers:
                    worker = self.workers[wid]
                    logger.warning(f"Worker {wid} timeout - removing")

                    # Re-queue assigned work
                    with self.work_lock:
                        for work_id in worker.assigned_work:
                            if work_id in self.pending_work:
                                self.work_queue.put(self.pending_work[work_id])

                    try:
                        worker.conn.close()
                    except:
                        pass

                    del self.workers[wid]
