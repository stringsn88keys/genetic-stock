@echo off
REM Windows launcher for distributed training worker

echo ================================================================================
echo Distributed Genetic Training - Worker Node (Windows)
echo ================================================================================
echo.

if "%1"=="" (
    echo Usage: run_distributed_worker.bat ^<server_ip^> [options]
    echo.
    echo Examples:
    echo   run_distributed_worker.bat localhost
    echo   run_distributed_worker.bat 192.168.1.100
    echo   run_distributed_worker.bat 192.168.1.100 --port 9999
    echo   run_distributed_worker.bat 192.168.1.100 --workers 8 --no-gpu
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment if it exists
if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Run the worker script
python scripts\train_distributed_worker.py %*

pause
