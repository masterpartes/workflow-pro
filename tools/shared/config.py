"""
Shared config for all Masterpartes tools.
Loads from .env file next to this repo root — never hardcode credentials.
"""
import os, re, sys
from pathlib import Path
from dotenv import load_dotenv

# Repo root = parent of tools/
REPO_ROOT  = Path(__file__).resolve().parent.parent.parent
TOOLS_DIR  = REPO_ROOT / "tools"
AGENT_DIR  = REPO_ROOT / "agent"
EXCEL_FILE = REPO_ROOT / "cotizacion_bulk.xlsm"
AVK_LIST_FILE = REPO_ROOT / "avk_parts_list.txt"
PARTSOUQ_LIST_FILE = REPO_ROOT / "partsouq_parts_list.txt"

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


# European vehicle-manufacturer names, as they show up in Inpart's "armadora"
# field (free text). Matched after stripping everything but letters, so
# "Mercedes-Benz" / "MERCEDES BENZ" / "mercedesbenz" all match the same way.
EUROPEAN_BRAND_NAMES = {
    "VW", "VOLKSWAGEN", "AUDI", "BMW", "MINI",
    "MERCEDES", "MERCEDESBENZ",
    "VOLVO", "JAGUAR", "LANDROVER", "LAND ROVER",
    "PORSCHE", "RENAULT", "CITROEN", "CITROËN", "PEUGEOT", "DS",
    "ALFAROMEO", "ALFA ROMEO", "FIAT", "FERRARI", "MASERATI", "MCLAREN",
    "SEAT", "SKODA", "OPEL", "SMART",
}


def _norm_brand(text: str) -> str:
    return re.sub(r"[^A-Z]", "", (text or "").upper())


_EUROPEAN_BRAND_NAMES_NORM = {_norm_brand(b) for b in EUROPEAN_BRAND_NAMES}


# Brands that have dedicated US OEM parts sites.  For these, the US site is
# always tried first regardless of VIN origin — "if the VIN is not recognised
# on the corresponding USA OEM site then it is a European vehicle."
# Without a VIN we can't confirm European assembly, so we default to trying
# the US site (it will simply return not-found for truly European-market parts).
_BRANDS_WITH_US_SITES_NORM = {_norm_brand(b) for b in {
    "MERCEDES", "MERCEDES BENZ",
    "BMW", "MINI",
    "AUDI",
    "VW", "VOLKSWAGEN",
    "VOLVO",
    "JAGUAR",
    "LAND ROVER", "LANDROVER",
    "PORSCHE",
}}


def is_european(vin: str = "", armadora: str = "") -> bool:
    """
    Decide whether a quote is for a European-brand vehicle -- i.e. whether
    it should route to AVK (European bulk parts search) instead of the
    US-market OEM scrapers / PartSouq.

    For brands that have US OEM parts sites (Mercedes, BMW, Audi, VW, Volvo,
    Jaguar, Land Rover, Porsche), the US site is always tried first:
      - VIN present  → WMI decides: US-assembled → False, European-built → True
      - VIN absent   → default False (try US site; returns not-found if European)

    For all other brands, armadora name is authoritative when present; VIN WMI
    is a fallback for quotes where armadora wasn't captured.
    """
    norm = _norm_brand(armadora)
    if norm:
        if norm in _BRANDS_WITH_US_SITES_NORM:
            # Has a US site → only route to AVK when VIN confirms European plant
            return is_european_vin(vin) if vin else False
        return norm in _EUROPEAN_BRAND_NAMES_NORM
    return is_european_vin(vin)
