@echo off
REM Windows launcher for distributed training leader

echo ================================================================================
echo Distributed Genetic Training - Leader Node (Windows)
echo ================================================================================
echo.

REM Activate virtual environment if it exists
if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Run the leader script
python scripts\train_distributed_leader.py %*

pause
