@echo off
echo Setting up Unicode support for Django...
chcp 65001 > nul
set PYTHONIOENCODING=utf-8

echo Starting Django ASGI server with WebSocket support...
daphne -b 127.0.0.1 -p 8000 login_backend.asgi:application

pause