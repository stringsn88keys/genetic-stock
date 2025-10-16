# Distributed Training Guide

This guide explains how to use the distributed training system to train genetic algorithms across multiple machines, utilizing all available CPU cores and GPUs.

## Overview

The distributed training system uses a leader-worker architecture:

- **Leader Node**: Runs the training server, coordinates the population evolution, and optionally participates as a worker
- **Worker Nodes**: Connect to the leader and process fitness evaluations (backtests) in parallel

### Architecture

```
┌─────────────────────────────────────────────────┐
│              Leader Node                        │
│  ┌───────────────────────────────────────────┐ │
│  │   Distributed Training Server             │ │
│  │   - Manages population                    │ │
│  │   - Distributes fitness evaluations       │ │
│  │   - Collects results                      │ │
│  │   - Performs evolution                    │ │
│  └───────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────┐ │
│  │   Local Worker (optional)                 │ │
│  │   - Uses local CPUs/GPUs                  │ │
│  └───────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
                    │
          ┌─────────┴─────────┐
          │                   │
┌─────────▼────────┐  ┌──────▼─────────┐
│  Worker Node 1   │  │  Worker Node 2 │
│  - 8 CPUs        │  │  - 16 CPUs     │
│  - 1 GPU         │  │  - 2 GPUs      │
└──────────────────┘  └────────────────┘
```

## Benefits

- **Faster Training**: Parallelize fitness evaluations across multiple machines
- **Utilize All Resources**: Use all CPUs and GPUs in your network
- **Scalability**: Add more workers dynamically as training progresses
- **Cross-Platform**: Works on Windows, Linux, and macOS
- **Fault Tolerance**: Workers can disconnect/reconnect without losing progress

## Prerequisites

### All Machines

1. Python 3.8+
2. Same version of the codebase
3. Same dependencies installed (see `requirements.txt`)
4. Network connectivity between machines

### Leader Machine

- Must have the training data in the cache database
- Sufficient disk space for checkpoints and results

### Worker Machines

- Do not need training data (will use data from cache or receive metadata)
- GPU is optional but recommended for faster processing

## Quick Start

### Step 1: Start the Leader

On the leader machine:

**Windows:**
```cmd
run_distributed_leader.bat
```

**Linux/macOS:**
```bash
./run_distributed_leader.sh
```

The leader will:
1. Start the distribution server
2. Load training data
3. Initialize the population
4. Start a local worker
5. Wait for remote workers to connect

### Step 2: Start Workers

On each worker machine, run:

**Windows:**
```cmd
run_distributed_worker.bat <leader_ip>
```

**Linux/macOS:**
```bash
./run_distributed_worker.sh <leader_ip>
```

Example:
```bash
./run_distributed_worker.sh 192.168.1.100
```

### Step 3: Monitor Progress

The leader will display:
- Generation progress
- Fitness statistics
- Worker count and activity
- Estimated completion time

## Configuration

### Leader Options

```bash
# Start leader on specific host/port
python scripts/train_distributed_leader.py --host 0.0.0.0 --port 9999

# Run specific number of generations
python scripts/train_distributed_leader.py --generations 100

# Server only (no local worker)
python scripts/train_distributed_leader.py --no-local-worker
```

### Worker Options

```bash
# Connect to leader with custom port
python scripts/train_distributed_worker.py 192.168.1.100 --port 9999

# Use specific number of CPU workers
python scripts/train_distributed_worker.py 192.168.1.100 --workers 8

# Disable GPU usage
python scripts/train_distributed_worker.py 192.168.1.100 --no-gpu
```

## Network Setup

### Finding Your IP Address

**Windows:**
```cmd
ipconfig
```
Look for "IPv4 Address" under your active network adapter.

**Linux/macOS:**
```bash
ip addr show    # Linux
ifconfig        # macOS
```
Look for the IP address on your active interface (e.g., `eth0`, `en0`).

### Firewall Configuration

The leader must allow incoming connections on the specified port (default: 9999).

**Windows Firewall:**
1. Open Windows Defender Firewall
2. Click "Advanced settings"
3. Create new Inbound Rule
4. Allow TCP port 9999

**Linux (ufw):**
```bash
sudo ufw allow 9999/tcp
```

**macOS:**
System Preferences → Security & Privacy → Firewall → Firewall Options → Add application/port

### Testing Connectivity

From a worker machine, test if you can reach the leader:

```bash
# Windows
telnet <leader_ip> 9999

# Linux/macOS
nc -zv <leader_ip> 9999
```

## Advanced Usage

### Running Multiple Workers on Same Machine

You can run multiple worker instances on the same machine to utilize different resources:

```bash
# Terminal 1: GPU worker
python scripts/train_distributed_worker.py localhost --workers 4

# Terminal 2: CPU-only worker
python scripts/train_distributed_worker.py localhost --workers 4 --no-gpu
```

### Resume from Checkpoint

If training is interrupted, you can resume from the last checkpoint:

```bash
# TODO: Add checkpoint resume functionality
```

### Dynamic Worker Scaling

Workers can join or leave during training:

- **Adding workers**: Simply start new workers - they will immediately begin processing work
- **Removing workers**: Press Ctrl+C - any assigned work will be re-queued automatically

## Monitoring and Debugging

### Log Files

- Leader: `logs/distributed_training_leader.log`
- Workers: `logs/distributed_worker.log`

### Common Issues

#### Worker Cannot Connect

1. Check leader is running
2. Verify IP address is correct
3. Check firewall allows port 9999
4. Test connectivity: `telnet <leader_ip> 9999`

#### Slow Performance

1. Check network latency between machines
2. Verify workers have sufficient CPU/memory
3. Monitor resource usage: `top` (Linux/macOS) or Task Manager (Windows)
4. Consider adjusting `--workers` parameter

#### Workers Disconnecting

1. Check network stability
2. Look for errors in worker logs
3. Ensure machines are not going to sleep
4. Verify sufficient memory available

## Performance Optimization

### Leader Machine

- Use SSD for faster checkpoint I/O
- Ensure sufficient RAM for population size
- Fast network connection recommended

### Worker Machines

- More CPU cores = more parallel evaluations
- GPU significantly speeds up backtesting
- Low-latency network connection preferred

### Scaling Guidelines

| Population Size | Recommended Workers | Expected Speedup |
|----------------|---------------------|------------------|
| 100            | 2-4 workers         | 2-3x            |
| 500            | 4-8 workers         | 4-6x            |
| 1000           | 8-16 workers        | 6-10x           |
| 5000           | 16-32 workers       | 10-20x          |

## Security Considerations

⚠️ **Important**: The distributed training system does not include encryption or authentication.

**Recommendations:**

1. Only use on trusted networks (home/private networks)
2. Use VPN for connections over internet
3. Use firewall rules to restrict access
4. Do not expose to public internet

## Example Setups

### Home Lab (3 Machines)

**Machine 1 (Leader):**
- Desktop PC: 8-core CPU, RTX 3080
- Role: Leader + Worker
```bash
./run_distributed_leader.sh
```

**Machine 2 (Worker):**
- Laptop: 4-core CPU, integrated GPU
- Role: Worker only
```bash
./run_distributed_worker.sh 192.168.1.100 --workers 4
```

**Machine 3 (Worker):**
- Old desktop: 6-core CPU, no GPU
- Role: CPU worker only
```bash
./run_distributed_worker.sh 192.168.1.100 --workers 6 --no-gpu
```

### Cloud Setup (AWS/GCP/Azure)

1. Launch multiple instances in same VPC
2. Ensure security group allows port 9999
3. Use private IP addresses for communication
4. Consider using spot/preemptible instances for workers

**Leader Instance:**
- c5.2xlarge (8 vCPUs) or similar

**Worker Instances:**
- 2-4x c5.xlarge (4 vCPUs) or similar
- p3.2xlarge if GPU acceleration desired

## Troubleshooting Commands

```bash
# Check if port is in use
netstat -an | grep 9999          # Linux/macOS
netstat -an | findstr 9999       # Windows

# Monitor network traffic
tcpdump -i any port 9999         # Linux (requires root)

# Check Python processes
ps aux | grep python             # Linux/macOS
tasklist | findstr python        # Windows

# Kill stuck processes
pkill -f train_distributed       # Linux/macOS
taskkill /F /FI "IMAGENAME eq python.exe"  # Windows
```

## FAQ

**Q: Can I mix Windows and Linux workers?**
A: Yes! The system is fully cross-platform compatible.

**Q: How many workers should I use?**
A: Use as many as you have machines available. Each worker can process multiple evaluations in parallel based on CPU count.

**Q: Do workers need the training data?**
A: Workers will attempt to load from local cache. If not available, they can work with provided metadata.

**Q: Can I run this over the internet?**
A: Technically yes, but it's not recommended due to security concerns. Use VPN if needed.

**Q: What happens if a worker crashes?**
A: Its assigned work will be automatically re-queued and processed by other workers.

**Q: Can I add workers mid-training?**
A: Yes! New workers can join at any time and will immediately begin processing work.

## Support

For issues or questions:
1. Check the log files
2. Review this documentation
3. Open an issue on GitHub
4. Check existing issues for solutions

## References

- [Main README](README.md)
- [Configuration Guide](config/config.yaml)
- [Training Guide](QUICKSTART.md)
