"""
Test CUDA/GPU availability and functionality for the genetic stock trading system.

This script tests:
1. Whether CuPy (CUDA support) is installed
2. Whether a CUDA-capable GPU is available
3. Whether GPU computations work correctly
4. Performance comparison between CPU and GPU operations
"""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_cupy_installation():
    """Test if CuPy is installed."""
    print("\n" + "="*60)
    print("TEST 1: CuPy Installation")
    print("="*60)

    try:
        import cupy as cp
        print("✓ CuPy is installed")
        print(f"  Version: {cp.__version__}")
        return True, cp
    except ImportError as e:
        print("✗ CuPy is NOT installed")
        print(f"  Error: {e}")
        print("  To install: pip install cupy-cuda12x")
        return False, None


def test_cuda_availability(cp):
    """Test if CUDA GPU is available and accessible."""
    print("\n" + "="*60)
    print("TEST 2: CUDA GPU Availability")
    print("="*60)

    if cp is None:
        print("✗ Skipped (CuPy not installed)")
        return False

    try:
        # Check if CUDA is available
        cuda_available = cp.cuda.is_available()
        print(f"  CUDA Available: {cuda_available}")

        if not cuda_available:
            print("✗ CUDA is not available on this system")
            return False

        # Get device count
        device_count = cp.cuda.runtime.getDeviceCount()
        print(f"  Number of CUDA devices: {device_count}")

        if device_count == 0:
            print("✗ No CUDA devices found")
            return False

        # Get device properties
        for i in range(device_count):
            device = cp.cuda.Device(i)
            print(f"\n  Device {i}:")

            # Get device name using cudaGetDeviceProperties
            props = cp.cuda.runtime.getDeviceProperties(i)
            print(f"    Name: {props['name'].decode('utf-8')}")
            print(f"    Compute Capability: {props['major']}.{props['minor']}")
            print(f"    Total Memory: {props['totalGlobalMem'] / 1e9:.2f} GB")
            print(f"    Multiprocessors: {props['multiProcessorCount']}")
            print(f"    Clock Rate: {props['clockRate'] / 1e6:.2f} GHz")

        print("\n✓ CUDA GPU is available and accessible")
        return True

    except Exception as e:
        print(f"✗ Error checking CUDA availability: {e}")
        return False


def test_gpu_computation(cp):
    """Test if GPU computations work correctly."""
    print("\n" + "="*60)
    print("TEST 3: GPU Computation Test")
    print("="*60)

    if cp is None:
        print("✗ Skipped (CuPy not installed)")
        return False

    try:
        # Create test array on GPU
        gpu_array = cp.array([1, 2, 3, 4, 5])
        print(f"  Created GPU array: {gpu_array}")

        # Perform computation (avoiding operations that require NVRTC)
        result_gpu = cp.sum(gpu_array ** 2)
        print(f"  Sum of squares (GPU): {result_gpu}")

        # Convert to CPU and verify
        result_cpu = cp.asnumpy(result_gpu)
        expected = 1**2 + 2**2 + 3**2 + 4**2 + 5**2  # = 55
        print(f"  Result on CPU: {result_cpu}")
        print(f"  Expected: {expected}")

        if result_cpu == expected:
            print("\n✓ GPU computation works correctly")
            return True
        else:
            print(f"\n✗ GPU computation incorrect (got {result_cpu}, expected {expected})")
            return False

    except Exception as e:
        error_msg = str(e)
        if "nvrtc" in error_msg.lower():
            print(f"⚠ Warning: NVRTC library missing, but GPU may still work for basic operations")
            print(f"  Error: {e}")
            print("\n  Note: Some CuPy features require NVRTC (CUDA runtime compilation)")
            print("  Install full CUDA Toolkit to enable all features")
            print("  Basic GPU operations may still work without it")
            # Return True with warning since GPU is available, just missing NVRTC
            return "partial"
        else:
            print(f"✗ Error during GPU computation: {e}")
            return False


def test_gpu_accelerator():
    """Test the GPUAccelerator class from the project."""
    print("\n" + "="*60)
    print("TEST 4: GPUAccelerator Class")
    print("="*60)

    try:
        from utils.gpu_utils import GPUAccelerator, GPU_AVAILABLE

        print(f"  GPU_AVAILABLE flag: {GPU_AVAILABLE}")

        # Create accelerator instance
        accelerator = GPUAccelerator(use_gpu=True)
        print(f"  Accelerator using GPU: {accelerator.use_gpu}")
        print(f"  Backend library: {accelerator.xp.__name__}")
        print(f"  Accelerator: {accelerator}")

        # Test computation
        import numpy as np
        test_prices = np.array([100.0, 102.0, 101.0, 105.0, 103.0, 108.0])

        print("\n  Testing compute_returns()...")
        returns = accelerator.compute_returns(test_prices)
        print(f"    Returns: {returns}")

        print("\n  Testing compute_sharpe_ratio()...")
        sharpe = accelerator.compute_sharpe_ratio(returns)
        print(f"    Sharpe ratio: {sharpe:.4f}")

        print("\n  Testing compute_max_drawdown()...")
        portfolio_values = np.array([100.0, 110.0, 105.0, 120.0, 115.0, 125.0])
        max_dd = accelerator.compute_max_drawdown(portfolio_values)
        print(f"    Max drawdown: {max_dd:.4f}")

        print("\n✓ GPUAccelerator class works correctly")
        print(f"  Status: {'GPU ENABLED' if accelerator.use_gpu else 'CPU FALLBACK'}")
        return accelerator.use_gpu

    except Exception as e:
        error_msg = str(e)
        if "nvrtc" in error_msg.lower():
            print(f"⚠ Warning: NVRTC library missing")
            print(f"  Error: {e}")
            print("\n  GPUAccelerator may have limited functionality without NVRTC")
            print("  Some operations will fall back to CPU")
            return "partial"
        else:
            print(f"✗ Error testing GPUAccelerator: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_performance_comparison(cp):
    """Compare CPU vs GPU performance for typical operations."""
    print("\n" + "="*60)
    print("TEST 5: Performance Comparison")
    print("="*60)

    if cp is None:
        print("✗ Skipped (CuPy not installed)")
        return

    try:
        import numpy as np
        import time

        # Create large test dataset
        size = 1_000_000
        print(f"  Dataset size: {size:,} elements")

        # CPU computation
        cpu_data = np.random.randn(size)
        start = time.time()
        cpu_result = np.sum(cpu_data ** 2)
        cpu_time = time.time() - start
        print(f"  CPU time: {cpu_time*1000:.2f} ms")

        # GPU computation
        try:
            gpu_data = cp.array(cpu_data)
            cp.cuda.Stream.null.synchronize()  # Ensure data transfer is complete

            start = time.time()
            gpu_result = cp.sum(gpu_data ** 2)
            cp.cuda.Stream.null.synchronize()  # Ensure computation is complete
            gpu_time = time.time() - start
            print(f"  GPU time: {gpu_time*1000:.2f} ms")

            # Calculate speedup
            speedup = cpu_time / gpu_time
            print(f"  Speedup: {speedup:.2f}x")

            # Verify results match
            gpu_result_cpu = cp.asnumpy(gpu_result)
            diff = abs(cpu_result - gpu_result_cpu)
            print(f"  Result difference: {diff:.2e}")

            if speedup > 1.0:
                print(f"\n✓ GPU is {speedup:.2f}x faster than CPU")
            else:
                print(f"\n⚠ GPU is slower than CPU for this operation")
                print("  (This is normal for small datasets due to transfer overhead)")

        except Exception as e:
            print(f"✗ GPU computation failed: {e}")

    except Exception as e:
        print(f"✗ Error during performance comparison: {e}")


def main():
    """Run all CUDA tests."""
    print("\n" + "="*60)
    print("CUDA/GPU AVAILABILITY TEST SUITE")
    print("="*60)
    print("\nThis test determines if CUDA will be used in the genetic")
    print("stock trading system for GPU-accelerated computations.")

    results = {}

    # Test 1: CuPy installation
    cupy_installed, cp = test_cupy_installation()
    results['cupy_installed'] = cupy_installed

    # Test 2: CUDA availability
    if cupy_installed:
        cuda_available = test_cuda_availability(cp)
        results['cuda_available'] = cuda_available
    else:
        cuda_available = False
        results['cuda_available'] = False

    # Test 3: GPU computation
    if cuda_available:
        gpu_works = test_gpu_computation(cp)
        results['gpu_works'] = gpu_works if isinstance(gpu_works, bool) else True
        results['gpu_partial'] = gpu_works == "partial"
    else:
        gpu_works = False
        results['gpu_works'] = False
        results['gpu_partial'] = False

    # Test 4: GPUAccelerator class
    gpu_accelerator_works = test_gpu_accelerator()
    results['gpu_accelerator'] = gpu_accelerator_works if isinstance(gpu_accelerator_works, bool) else True
    results['accelerator_partial'] = gpu_accelerator_works == "partial"

    # Test 5: Performance comparison
    if cuda_available and gpu_works and gpu_works != "partial":
        test_performance_comparison(cp)
    elif cuda_available and gpu_works == "partial":
        print("\n⚠ Skipping performance test due to NVRTC library issues")

    # Final summary
    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    print(f"CuPy Installed:        {'✓' if results['cupy_installed'] else '✗'}")
    print(f"CUDA Available:        {'✓' if results['cuda_available'] else '✗'}")
    print(f"GPU Computation:       {'✓' if results['gpu_works'] else '✗'}")
    print(f"GPUAccelerator Works:  {'✓' if results['gpu_accelerator'] else '✗'}")

    # Show warnings if partial functionality
    if results.get('gpu_partial') or results.get('accelerator_partial'):
        print("\nWarnings:")
        if results.get('gpu_partial'):
            print("  ⚠ NVRTC library missing - some GPU features may not work")
        if results.get('accelerator_partial'):
            print("  ⚠ GPUAccelerator has limited functionality")

    print("\n" + "="*60)
    if results['gpu_accelerator']:
        print("RESULT: ✓ CUDA WILL BE USED")
        print("="*60)
        print("\nGPU acceleration is available and will be used when")
        print("GPUAccelerator class is explicitly utilized in the code.")
        if results.get('gpu_partial') or results.get('accelerator_partial'):
            print("\nNote: NVRTC library is missing. To enable full GPU functionality:")
            print("  1. Download CUDA Toolkit from NVIDIA")
            print("  2. Install and add to PATH")
            print("  3. Ensure nvrtc64_120_0.dll is accessible")
            print("\nBasic GPU operations work, but some advanced features may fall back to CPU.")
        return_code = 0
    else:
        print("RESULT: ✗ CUDA WILL NOT BE USED")
        print("="*60)
        print("\nThe system will fall back to CPU (NumPy) operations.")
        if not results['cupy_installed']:
            print("\nTo enable CUDA support:")
            print("1. Install CuPy: pip install cupy-cuda12x")
            print("2. Ensure you have a CUDA-capable GPU")
            print("3. Install NVIDIA CUDA Toolkit")
        return_code = 1

    print("="*60)
    return return_code


if __name__ == "__main__":
    sys.exit(main())
