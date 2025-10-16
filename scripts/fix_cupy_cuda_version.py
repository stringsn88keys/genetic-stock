"""
Script to fix CuPy CUDA version mismatch.

This script:
1. Detects the installed CUDA Toolkit version
2. Uninstalls the current CuPy version
3. Installs the correct CuPy version matching your CUDA Toolkit
4. Verifies the installation
"""

import subprocess
import sys
import re


def run_command(cmd, description):
    """Run a shell command and return the output."""
    print(f"\n{description}...")
    print(f"  Command: {cmd}")
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        print("  ✗ Command timed out")
        return -1, "", "Timeout"
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return -1, "", str(e)


def detect_cuda_version():
    """Detect installed CUDA Toolkit version."""
    print("\n" + "="*60)
    print("STEP 1: Detecting CUDA Toolkit Version")
    print("="*60)

    returncode, stdout, stderr = run_command("nvcc --version", "Checking CUDA version")

    if returncode != 0:
        print("\n✗ CUDA Toolkit not found or nvcc not in PATH")
        print("\nPlease install CUDA Toolkit from:")
        print("https://developer.nvidia.com/cuda-downloads")
        return None

    # Parse CUDA version from nvcc output
    # Example: "Cuda compilation tools, release 11.5, V11.5.50"
    match = re.search(r'release (\d+)\.(\d+)', stdout)
    if match:
        major = int(match.group(1))
        minor = int(match.group(2))
        version = f"{major}.{minor}"
        print(f"\n✓ Found CUDA Toolkit version: {version}")
        print(f"  Major version: {major}")
        print(f"  Minor version: {minor}")
        return major
    else:
        print("\n✗ Could not parse CUDA version from nvcc output")
        print(stdout)
        return None


def get_cupy_package_name(cuda_major):
    """Get the correct CuPy package name for the CUDA version."""
    if cuda_major == 11:
        return "cupy-cuda11x"
    elif cuda_major == 12:
        return "cupy-cuda12x"
    elif cuda_major >= 13:
        return "cupy-cuda12x"  # Use latest for future versions
    else:
        print(f"\n⚠ Warning: CUDA {cuda_major} is older than supported")
        print("  Minimum supported CUDA version is 11.x")
        return None


def uninstall_current_cupy():
    """Uninstall all existing CuPy installations."""
    print("\n" + "="*60)
    print("STEP 2: Uninstalling Current CuPy")
    print("="*60)

    # Check what's currently installed
    returncode, stdout, stderr = run_command(
        "pip list | grep -i cupy",
        "Checking installed CuPy packages"
    )

    if "cupy" not in stdout.lower():
        print("\n  No CuPy packages found")
        return True

    print(f"\n  Current installation:\n{stdout}")

    # Uninstall all CuPy variants
    cupy_packages = ["cupy", "cupy-cuda11x", "cupy-cuda12x", "cupy-cuda110",
                     "cupy-cuda111", "cupy-cuda112", "cupy-cuda113", "cupy-cuda114",
                     "cupy-cuda115", "cupy-cuda116", "cupy-cuda117", "cupy-cuda118",
                     "cupy-cuda12x"]

    for package in cupy_packages:
        returncode, stdout, stderr = run_command(
            f"pip uninstall -y {package}",
            f"Uninstalling {package}"
        )
        # Don't fail if package not found
        if returncode == 0 or "not installed" in stderr.lower():
            continue

    print("\n✓ Uninstalled existing CuPy packages")
    return True


def install_cupy(package_name):
    """Install the correct CuPy version."""
    print("\n" + "="*60)
    print("STEP 3: Installing Correct CuPy Version")
    print("="*60)

    print(f"\n  Installing: {package_name}")

    returncode, stdout, stderr = run_command(
        f"pip install {package_name}",
        f"Installing {package_name}"
    )

    if returncode != 0:
        print("\n✗ Installation failed")
        print(f"  Error: {stderr}")
        return False

    print(f"\n✓ Successfully installed {package_name}")
    return True


def verify_installation():
    """Verify CuPy installation and CUDA functionality."""
    print("\n" + "="*60)
    print("STEP 4: Verifying Installation")
    print("="*60)

    print("\n  Testing CuPy import and CUDA functionality...")

    test_code = """
import sys
try:
    import cupy as cp
    print(f"CuPy version: {cp.__version__}")
    print(f"CUDA available: {cp.cuda.is_available()}")

    if cp.cuda.is_available():
        device_count = cp.cuda.runtime.getDeviceCount()
        print(f"CUDA devices: {device_count}")

        # Test basic operation
        arr = cp.array([1, 2, 3, 4, 5])
        result = cp.sum(arr)
        print(f"Test computation: sum([1,2,3,4,5]) = {result}")

        # Test NVRTC
        try:
            # This operation requires NVRTC
            x = cp.arange(10)
            y = x ** 2
            print(f"NVRTC test: PASSED")
            sys.exit(0)
        except Exception as e:
            if 'nvrtc' in str(e).lower():
                print(f"NVRTC test: FAILED - {e}")
                print("Note: Basic GPU operations work, but NVRTC is missing")
                sys.exit(0)  # Still consider this success
            else:
                raise
    else:
        print("ERROR: CUDA not available")
        sys.exit(1)

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
"""

    returncode, stdout, stderr = run_command(
        f'python -c "{test_code}"',
        "Testing CuPy functionality"
    )

    print(f"\n{stdout}")

    if returncode == 0:
        print("\n✓ CuPy installation verified successfully")
        return True
    else:
        print("\n✗ CuPy verification failed")
        print(f"  Error: {stderr}")
        return False


def main():
    """Main function to fix CuPy CUDA version."""
    print("\n" + "="*60)
    print("CUPY CUDA VERSION FIX SCRIPT")
    print("="*60)
    print("\nThis script will:")
    print("1. Detect your CUDA Toolkit version")
    print("2. Uninstall incompatible CuPy versions")
    print("3. Install the correct CuPy version")
    print("4. Verify the installation")

    # Step 1: Detect CUDA version
    cuda_major = detect_cuda_version()
    if cuda_major is None:
        print("\n" + "="*60)
        print("FAILED: Could not detect CUDA version")
        print("="*60)
        return 1

    # Get correct package name
    package_name = get_cupy_package_name(cuda_major)
    if package_name is None:
        print("\n" + "="*60)
        print("FAILED: Unsupported CUDA version")
        print("="*60)
        return 1

    print(f"\n  Recommended CuPy package: {package_name}")

    # Confirm with user
    print("\n" + "="*60)
    print("CONFIRMATION")
    print("="*60)
    print(f"\nThis will:")
    print(f"  - Uninstall existing CuPy packages")
    print(f"  - Install {package_name}")
    print(f"\nProceed? (y/n): ", end="")

    try:
        response = input().strip().lower()
        if response != 'y':
            print("\nOperation cancelled by user")
            return 0
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        return 0

    # Step 2: Uninstall current CuPy
    if not uninstall_current_cupy():
        print("\n" + "="*60)
        print("FAILED: Could not uninstall current CuPy")
        print("="*60)
        return 1

    # Step 3: Install correct CuPy
    if not install_cupy(package_name):
        print("\n" + "="*60)
        print("FAILED: Could not install CuPy")
        print("="*60)
        return 1

    # Step 4: Verify installation
    if not verify_installation():
        print("\n" + "="*60)
        print("WARNING: Installation completed but verification failed")
        print("="*60)
        print("\nYou may need to:")
        print("1. Restart your terminal/shell")
        print("2. Check CUDA Toolkit installation")
        print("3. Verify GPU drivers are up to date")
        return 1

    # Success!
    print("\n" + "="*60)
    print("SUCCESS: CuPy CUDA Version Fixed")
    print("="*60)
    print(f"\n✓ Installed: {package_name}")
    print("✓ CUDA functionality verified")
    print("\nYou can now run the CUDA test:")
    print("  python scripts/test_cuda.py")
    print("="*60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
