@echo off
REM Auto-cancel expired payment reservations
REM This script should be run every 15 minutes via Windows Task Scheduler

cd /d "%~dp0"
D:\JHONLOYD\DORM_FINDER\venv\Scripts\python.exe manage.py cancel_expired_payments

REM Log the execution
echo Ran cancel_expired_payments at %date% %time% >> logs\cancel_expired.log
