"""Distributed training worker script - connects to leader and processes workloads"""

import sys
import os
import logging
import argparse
import time

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.distributed.client import DistributedClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/distributed_worker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description='Distributed Genetic Training Worker',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Connect to leader on same machine
  python train_distributed_worker.py localhost

  # Connect to remote leader
  python train_distributed_worker.py 192.168.1.100

  # Connect to remote leader with custom port
  python train_distributed_worker.py 192.168.1.100 --port 9999

  # Use specific number of CPU workers
  python train_distributed_worker.py 192.168.1.100 --workers 8

  # Disable GPU usage
  python train_distributed_worker.py localhost --no-gpu
        """
    )

    parser.add_argument('server_host',
                       help='Leader server hostname or IP address (e.g., 192.168.1.100)')
    parser.add_argument('--port', type=int, default=9999,
                       help='Server port (default: 9999)')
    parser.add_argument('--workers', type=int, default=None,
                       help='Number of worker processes (default: CPU count)')
    parser.add_argument('--no-gpu', action='store_true',
                       help='Disable GPU usage')

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("DISTRIBUTED GENETIC TRAINING - WORKER NODE")
    logger.info("=" * 80)

    logger.info(f"Configuration:")
    logger.info(f"  - Server: {args.server_host}:{args.port}")
    logger.info(f"  - Workers: {args.workers or 'CPU count'}")
    logger.info(f"  - GPU Enabled: {not args.no_gpu}")

    # Create client
    client = DistributedClient(
        server_host=args.server_host,
        server_port=args.port,
        num_workers=args.workers,
        use_gpu=not args.no_gpu
    )

    # Connect to server
    logger.info(f"\nConnecting to leader at {args.server_host}:{args.port}...")

    max_retries = 5
    retry_delay = 5

    for attempt in range(max_retries):
        if client.connect():
            logger.info("Successfully connected to leader\n")
            break
        else:
            if attempt < max_retries - 1:
                logger.warning(f"Connection failed, retrying in {retry_delay}s "
                             f"({attempt + 1}/{max_retries})...")
                time.sleep(retry_delay)
            else:
                logger.error("Failed to connect to leader after multiple attempts")
                logger.error("\nTroubleshooting:")
                logger.error("  1. Check that the leader is running")
                logger.error("  2. Verify the hostname/IP address is correct")
                logger.error("  3. Ensure the port is not blocked by firewall")
                logger.error(f"  4. Test connection: telnet {args.server_host} {args.port}")
                return 1

    # Start processing work
    logger.info("Starting work processing...")
    logger.info("Press Ctrl+C to stop the worker\n")

    try:
        client.start()

    except KeyboardInterrupt:
        logger.info("\n\nWorker stopped by user")

    except Exception as e:
        logger.error(f"\nError: {e}", exc_info=True)
        return 1

    finally:
        # Print statistics
        stats = client.get_statistics()
        logger.info("\n" + "=" * 80)
        logger.info("WORKER STATISTICS")
        logger.info("=" * 80)
        logger.info(f"Work Completed:  {stats['work_completed']}")
        logger.info(f"Work Failed:     {stats['work_failed']}")
        logger.info(f"Total Time:      {stats['total_execution_time']:.1f}s")
        logger.info(f"Uptime:          {stats['uptime']:.1f}s")
        if stats['work_completed'] > 0:
            avg_time = stats['total_execution_time'] / stats['work_completed']
            logger.info(f"Avg Work Time:   {avg_time:.2f}s")
        logger.info("=" * 80)

    return 0


if __name__ == '__main__':
    # Create logs directory
    os.makedirs('logs', exist_ok=True)

    sys.exit(main())
