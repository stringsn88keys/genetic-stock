"""Distributed training client for processing workloads"""

import socket
import logging
import time
import threading
import platform
import os
import sys
from typing import Optional, Dict, Any
import multiprocessing as mp

from .protocol import (
    Message, MessageType, WorkUnit, WorkResult, WorkerInfo,
    send_message, receive_message
)

logger = logging.getLogger(__name__)


class DistributedClient:
    """Client worker for processing distributed training workloads"""

    def __init__(self, server_host: str, server_port: int = 9999,
                 num_workers: Optional[int] = None,
                 use_gpu: bool = True):
        """
        Initialize distributed training client

        Args:
            server_host: Server hostname or IP address
            server_port: Server port
            num_workers: Number of worker processes (default: CPU count)
            use_gpu: Whether to use GPU if available
        """
        self.server_host = server_host
        self.server_port = server_port
        self.num_workers = num_workers or mp.cpu_count()
        self.use_gpu = use_gpu

        self.socket = None
        self.worker_id = None
        self.running = False

        # Worker info
        self.worker_info = self._gather_worker_info()

        # Statistics
        self.stats = {
            'work_completed': 0,
            'work_failed': 0,
            'total_execution_time': 0.0,
            'connected_time': 0.0
        }

        # For local execution
        self.config = None
        self.train_data = None

    def connect(self) -> bool:
        """
        Connect to the server

        Returns:
            True if connection successful
        """
        try:
            logger.info(f"Connecting to server at {self.server_host}:{self.server_port}")

            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server_host, self.server_port))
            self.socket.settimeout(10.0)

            # Send registration
            send_message(self.socket, Message(MessageType.REGISTER, self.worker_info))

            # Wait for acknowledgment
            msg = receive_message(self.socket)
            if not msg or msg.type != MessageType.REGISTER:
                logger.error("Failed to register with server")
                return False

            self.worker_id = msg.payload['worker_id']
            logger.info(f"Successfully registered with server as {self.worker_id}")

            self.running = True
            self.stats['connected_time'] = time.time()

            return True

        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            return False

    def disconnect(self):
        """Disconnect from server"""
        logger.info("Disconnecting from server")
        self.running = False

        if self.socket:
            try:
                self.socket.close()
            except:
                pass

        logger.info("Disconnected")

    def start(self):
        """Start processing work from server"""
        if not self.running:
            logger.error("Not connected to server")
            return

        logger.info(f"Starting worker with {self.num_workers} processes")

        # Start heartbeat thread
        heartbeat_thread = threading.Thread(target=self._send_heartbeats, daemon=True)
        heartbeat_thread.start()

        # Main work loop
        try:
            self.socket.settimeout(None)
            self._work_loop()

        except KeyboardInterrupt:
            logger.info("Worker interrupted by user")

        except Exception as e:
            logger.error(f"Error in worker loop: {e}")

        finally:
            self.disconnect()

    def set_training_data(self, config: Dict, train_data: Dict):
        """
        Set training data for local execution

        Args:
            config: Configuration dictionary
            train_data: Training data dictionary
        """
        self.config = config
        self.train_data = train_data
        logger.info("Training data set for local execution")

    def _work_loop(self):
        """Main work loop - request and process work"""
        while self.running:
            try:
                # Request work from server
                send_message(self.socket, Message(MessageType.WORK_REQUEST))

                # Wait for response
                msg = receive_message(self.socket)
                if not msg:
                    logger.warning("Lost connection to server")
                    break

                if msg.type == MessageType.SHUTDOWN:
                    logger.info("Server requested shutdown")
                    break

                elif msg.type == MessageType.NO_WORK:
                    # No work available, wait a bit
                    time.sleep(1.0)
                    continue

                elif msg.type == MessageType.WORK_ASSIGNED:
                    # Process the work
                    work_unit: WorkUnit = msg.payload
                    result = self._process_work(work_unit)

                    # Send result back
                    send_message(self.socket, Message(MessageType.WORK_RESULT, result))

                    # Update stats
                    if result.success:
                        self.stats['work_completed'] += 1
                        if result.execution_time:
                            self.stats['total_execution_time'] += result.execution_time
                    else:
                        self.stats['work_failed'] += 1

            except Exception as e:
                logger.error(f"Error in work loop: {e}")
                time.sleep(5.0)

    def _process_work(self, work_unit: WorkUnit) -> WorkResult:
        """
        Process a work unit

        Args:
            work_unit: Work unit to process

        Returns:
            Work result
        """
        start_time = time.time()

        try:
            logger.info(f"Processing work {work_unit.work_id} (type: {work_unit.work_type})")

            if work_unit.work_type == 'fitness_eval':
                result = self._evaluate_fitness(work_unit)
            else:
                raise ValueError(f"Unknown work type: {work_unit.work_type}")

            execution_time = time.time() - start_time
            logger.info(f"Completed work {work_unit.work_id} in {execution_time:.2f}s")

            return WorkResult(
                work_id=work_unit.work_id,
                worker_id=self.worker_id,
                success=True,
                fitness_score=result['fitness'],
                metrics=result.get('metrics'),
                execution_time=execution_time
            )

        except Exception as e:
            logger.error(f"Error processing work {work_unit.work_id}: {e}")
            execution_time = time.time() - start_time

            return WorkResult(
                work_id=work_unit.work_id,
                worker_id=self.worker_id,
                success=False,
                error=str(e),
                execution_time=execution_time
            )

    def _evaluate_fitness(self, work_unit: WorkUnit) -> Dict[str, Any]:
        """
        Evaluate fitness for a chromosome

        Args:
            work_unit: Work unit with chromosome data

        Returns:
            Dictionary with fitness score and metrics
        """
        # Import here to avoid circular dependencies
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from src.genetic.chromosome import Chromosome
        from src.trading.backtest import BacktestEngine

        # Reconstruct chromosome from data
        chromosome = Chromosome.from_dict(work_unit.chromosome_data)

        # Get config and data
        config = work_unit.config
        train_data_info = work_unit.train_data_info

        # If we have local training data, use it
        # Otherwise, would need to fetch from cache
        if self.train_data:
            train_data = self.train_data
        else:
            # Load data from cache
            from src.data.cache import DataCache
            cache = DataCache()
            train_data = {}
            for ticker in train_data_info['tickers']:
                df = cache.get_price_data(ticker)
                if not df.empty:
                    # Apply same filtering as in training
                    start_idx = train_data_info.get('start_idx', 0)
                    end_idx = train_data_info.get('end_idx', len(df))
                    train_data[ticker] = df.iloc[start_idx:end_idx]

        # Run backtest
        backtest = BacktestEngine(
            chromosome=chromosome,
            initial_capital=config['population']['initial_capital'],
            commission=config['trading'].get('commission', 0.0),
            slippage=config['trading'].get('slippage', 0.001),
            max_positions=config['trading'].get('max_positions', 10),
            min_cash_reserve=config['trading'].get('min_cash_reserve', 0.05)
        )

        for ticker, df in train_data.items():
            backtest.run(ticker, df)

        metrics = backtest.get_metrics()

        # Calculate fitness score
        sharpe = metrics.get('sharpe_ratio', 0)
        total_return = metrics.get('total_return', 0)
        max_drawdown = metrics.get('max_drawdown', 0)
        win_rate = metrics.get('win_rate', 0)

        fitness = (
            sharpe * 0.4 +
            total_return * 0.3 +
            (1.0 - abs(max_drawdown)) * 0.2 +
            win_rate * 0.1
        )

        return {
            'fitness': fitness,
            'metrics': metrics
        }

    def _send_heartbeats(self):
        """Send periodic heartbeats to server"""
        while self.running:
            try:
                send_message(self.socket, Message(MessageType.HEARTBEAT))
                time.sleep(10)
            except:
                break

    def _gather_worker_info(self) -> Dict[str, Any]:
        """Gather information about this worker"""
        gpu_count = 0
        gpu_names = []

        if self.use_gpu:
            try:
                import cupy as cp
                gpu_count = cp.cuda.runtime.getDeviceCount()
                for i in range(gpu_count):
                    props = cp.cuda.runtime.getDeviceProperties(i)
                    gpu_names.append(props['name'].decode('utf-8'))
            except:
                gpu_count = 0
                gpu_names = []

        return {
            'hostname': platform.node(),
            'platform': platform.system(),
            'cpu_count': self.num_workers,
            'gpu_available': gpu_count > 0,
            'gpu_count': gpu_count,
            'gpu_names': gpu_names
        }

    def get_statistics(self) -> Dict:
        """Get client statistics"""
        uptime = 0.0
        if self.stats['connected_time'] > 0:
            uptime = time.time() - self.stats['connected_time']

        return {
            **self.stats,
            'uptime': uptime,
            'worker_id': self.worker_id
        }
