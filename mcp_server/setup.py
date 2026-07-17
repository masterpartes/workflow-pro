r"""
setup.py — registers the Masterpartes MCP server in Claude Desktop.

Run once from PowerShell / Git Bash:
    cd C:\Users\Juan Guerra\Desktop\workflow-pro\mcp_server
    python setup.py

What it does:
  1. Reads %APPDATA%\Claude\claude_desktop_config.json (creates it if missing)
  2. Adds the "masterpartes" MCP server entry (local mode — no Railway)
  3. Writes the file back

After running: quit and relaunch Claude Desktop.
"""
import json
import os
import sys
from pathlib import Path

APPDATA = os.environ.get("APPDATA", "")
if not APPDATA:
    print("ERROR: %APPDATA% not set. Are you on Windows?")
    sys.exit(1)

CONFIG_PATH = Path(APPDATA) / "Claude" / "claude_desktop_config.json"
SERVER_PATH = Path(__file__).parent / "server.py"

NEW_SERVER = {
    "command": "python",
    "args": [str(SERVER_PATH)],
    # No env vars needed — credentials come from workflow-pro/.env
}

if CONFIG_PATH.exists():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        try:
            config = json.load(f)
        except json.JSONDecodeError:
            print(f"WARNING: {CONFIG_PATH} is invalid JSON — starting fresh.")
            config = {}
else:
    print(f"Config not found at {CONFIG_PATH} — creating it.")
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    config = {}

config.setdefault("mcpServers", {})
config["mcpServers"]["masterpartes"] = NEW_SERVER

with open(CONFIG_PATH, "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2)

print(f"\n✓ Config updated: {CONFIG_PATH}")
print(f"  Server script : {SERVER_PATH}")
print(f"  Mode          : local (no Railway)")
print()
print("Make sure workflow-pro/.env contains:")
print("  EBAY_APP_ID=...")
print("  EBAY_CERT_ID=...")
print()
print("Next steps:")
print("  1. Confirm .env has EBAY_APP_ID and EBAY_CERT_ID")
print("  2. Quit and relaunch Claude Desktop")
print("  3. Open the MASTERPARTESbot Project — tools appear automatically")
print()
print("MCP tools available:")
print("  • check_health       — verify local setup")
print("  • quote_parts        — OEM + eBay prices for a list of parts")
print("  • get_excel_parts    — read current parts from Excel")
print("  • generate_avk_list  — build AVK bulk-search list for European brands")
