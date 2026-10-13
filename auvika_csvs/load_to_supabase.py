"""
load_to_supabase.py  — ONE-TIME data load: auvika_prices_combined.csv → Supabase
Uses direct PostgreSQL COPY (streams the CSV in one shot — ~2-3 min for 7.5M rows).

Requirements:
    pip install psycopg2-binary

Run from PowerShell:
    cd C:\Users\Juan Guerra\Desktop\workflow-pro\auvika_csvs
    $env:SUPABASE_DB_PASSWORD = "your-db-password"
    python load_to_supabase.py

Find the DB password at:
    Supabase dashboard → Settings → Database → Connection string
    (the password is after "postgres:" and before "@")
"""

import os, sys, time

try:
    import psycopg2
except ImportError:
    print("Installing psycopg2-binary ...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary"])
    import psycopg2

DB_PASSWORD = os.environ.get("SUPABASE_DB_PASSWORD", "")
CSV_PATH    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auvika_prices_combined.csv")

if not DB_PASSWORD:
    print("\nERROR: Set your Supabase DB password first:")
    print('  $env:SUPABASE_DB_PASSWORD="your-password"   (PowerShell)')
    sys.exit(1)

if not os.path.exists(CSV_PATH):
    print(f"ERROR: CSV not found at {CSV_PATH}")
    sys.exit(1)

DSN = (
    f"host=db.hysmhkmqaijlglplckxq.supabase.co "
    f"port=5432 "
    f"dbname=postgres "
    f"user=postgres "
    f"password={DB_PASSWORD} "
    f"sslmode=require"
)

print("Connecting to Supabase PostgreSQL ...")
conn = psycopg2.connect(DSN)
conn.autocommit = False
cur = conn.cursor()

# Truncate first so re-runs are idempotent
print("Clearing existing rows ...")
cur.execute("TRUNCATE TABLE auvika_prices")

print(f"Streaming {CSV_PATH} via COPY ...")
t0 = time.monotonic()

with open(CSV_PATH, "r", encoding="utf-8") as f:
    cur.copy_expert(
        "COPY auvika_prices (oe, price_eur, manufacturer, source) "
        "FROM STDIN WITH (FORMAT CSV, HEADER TRUE, NULL '')",
        f,
    )

conn.commit()
elapsed = time.monotonic() - t0

cur.execute("SELECT COUNT(*) FROM auvika_prices")
count = cur.fetchone()[0]
cur.close()
conn.close()

print(f"\nDone! {count:,} rows loaded in {elapsed:.1f}s ({elapsed/60:.1f} min).")
print("Lookups are now live on Railway — no laptop needed.")
