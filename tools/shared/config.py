"""
Shared config for all Masterpartes tools.
Loads from .env file next to this repo root — never hardcode credentials.
"""
import os, sys
from pathlib import Path
from dotenv import load_dotenv

# Repo root = parent of tools/
REPO_ROOT  = Path(__file__).resolve().parent.parent.parent
TOOLS_DIR  = REPO_ROOT / "tools"
AGENT_DIR  = REPO_ROOT / "agent"
EXCEL_FILE = REPO_ROOT / "cotizacion_bulk.xlsm"
AVK_LIST_FILE = REPO_ROOT / "avk_parts_list.txt"

# Add agent/ to path so we can reuse ebay_service, oem_service
sys.path.insert(0, str(AGENT_DIR))

# Load .env from repo root
_env_path = REPO_ROOT / ".env"
load_dotenv(_env_path)

INPART_USERNAME   = os.environ.get("INPART_USERNAME", "")
INPART_PASSWORD   = os.environ.get("INPART_PASSWORD", "")
EBAY_APP_ID       = os.environ.get("EBAY_APP_ID", "")
EBAY_CERT_ID      = os.environ.get("EBAY_CERT_ID", "")
SUPABASE_URL      = os.environ.get("SUPABASE_URL", "https://hysmhkmqaijlglplckxq.supabase.co")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# European WMI prefixes → route to AVK bulk search
EUROPEAN_WMIS = {
    "WBA","WBX","WBS","5UX","4US",           # BMW
    "WAU","WA1",                              # Audi
    "WVW","1VW","3VW",                        # VW
    "WP0","WP1",                              # Porsche
    "SAJ",                                    # Jaguar
    "SAL","SAR",                              # Land Rover
    "YV1","YV4",                              # Volvo
    "WDB","WDD","WDC","WDF","WMX","WME",      # Mercedes-Benz (European-built passenger cars)
    "NW1","9BM","8AD",                         # Mercedes-Benz LatAm assembly (Actros trucks, Brazil, Argentina)
    "VF1","VF3","VF7",                        # Renault
    "VF6",                                    # Renault commercial
    "ZAR","ZFA","ZFF",                        # Alfa Romeo / Fiat / Ferrari
    "TRU","WUA",                              # Audi (TT)
    "SCC",                                    # McLaren
    "WP1",                                    # Porsche SUV
}

def is_european_vin(vin: str) -> bool:
    return bool(vin) and vin[:3].upper() in EUROPEAN_WMIS
