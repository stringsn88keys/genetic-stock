#!/bin/bash
# Linux/macOS launcher for distributed training leader

echo "================================================================================"
echo "Distributed Genetic Training - Leader Node (Linux/macOS)"
echo "================================================================================"
echo ""

# Activate virtual environment if it exists
if [ -f "venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Run the leader script
python scripts/train_distributed_leader.py "$@"
