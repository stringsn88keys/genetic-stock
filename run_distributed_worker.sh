#!/bin/bash
# Linux/macOS launcher for distributed training worker

echo "================================================================================"
echo "Distributed Genetic Training - Worker Node (Linux/macOS)"
echo "================================================================================"
echo ""

if [ -z "$1" ]; then
    echo "Usage: ./run_distributed_worker.sh <server_ip> [options]"
    echo ""
    echo "Examples:"
    echo "  ./run_distributed_worker.sh localhost"
    echo "  ./run_distributed_worker.sh 192.168.1.100"
    echo "  ./run_distributed_worker.sh 192.168.1.100 --port 9999"
    echo "  ./run_distributed_worker.sh 192.168.1.100 --workers 8 --no-gpu"
    echo ""
    exit 1
fi

# Activate virtual environment if it exists
if [ -f "venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Run the worker script
python scripts/train_distributed_worker.py "$@"
