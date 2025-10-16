# Distributed Training Quick Start

## Leader Machine (Where You Have the Data)

### Windows
```cmd
run_distributed_leader.bat
```

### Linux/macOS
```bash
./run_distributed_leader.sh
```

The leader will display its IP address. Note it down for workers.

---

## Worker Machines (Other Computers)

### Windows
```cmd
run_distributed_worker.bat <LEADER_IP>
```

### Linux/macOS
```bash
./run_distributed_worker.sh <LEADER_IP>
```

Replace `<LEADER_IP>` with the leader's IP address (e.g., `192.168.1.100`)

---

## Examples

### Leader
```bash
# Start leader on default settings
./run_distributed_leader.sh

# Start leader on specific port
python scripts/train_distributed_leader.py --port 8888

# Leader without local worker (pure server)
python scripts/train_distributed_leader.py --no-local-worker
```

### Workers
```bash
# Connect to leader at 192.168.1.100
./run_distributed_worker.sh 192.168.1.100

# Use 8 CPU workers
./run_distributed_worker.sh 192.168.1.100 --workers 8

# Disable GPU
./run_distributed_worker.sh 192.168.1.100 --no-gpu

# Custom port
./run_distributed_worker.sh 192.168.1.100 --port 8888
```

---

## Finding Your IP Address

### Windows
```cmd
ipconfig
```
Look for "IPv4 Address"

### Linux/macOS
```bash
hostname -I    # Linux
ifconfig       # macOS
```

---

## Firewall Setup

Allow incoming connections on port 9999 (or your custom port)

### Windows
Windows Defender Firewall → Allow an app → Port 9999

### Linux
```bash
sudo ufw allow 9999/tcp
```

---

## Monitoring

Watch the leader's console output for:
- Number of active workers
- Generation progress
- Fitness scores
- Estimated completion time

---

## Stopping

Press `Ctrl+C` on any worker or the leader to stop gracefully.

---

## Full Documentation

See [DISTRIBUTED_TRAINING.md](DISTRIBUTED_TRAINING.md) for complete guide.
