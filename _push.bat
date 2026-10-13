@echo off
cd /d "C:\Users\Juan Guerra\Desktop\workflow-pro"
del /f .git\HEAD.lock 2>nul
del /f .git\index.lock 2>nul
git add mcp_server\server.py mcp_server\setup.py
git commit -m "Rewrite MCP server as local-only — no Railway, calls oem_service/ebay_service directly"
git push origin main
echo.
echo Done. Press any key to close.
pause >nul
