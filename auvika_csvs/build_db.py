"""
build_db.py  — converts auvika_prices_combined.csv → auvika.db (SQLite)
Run from: C:\Users\Juan Guerra\Desktop\workflow-pro\auvika_csvs\
    python build_db.py
"""
import sqlite3, csv, time, os, sys

src = os.path.join(os.path.dirname(__file__), "auvika_prices_combined.csv")
dst = os.path.join(os.path.dirname(__file__), "auvika.db")

if not os.path.exists(src):
    print(f"ERROR: {src} not found"); sys.exit(1)

if os.path.exists(dst):
    os.remove(dst)
    print(f"Removed old {dst}")

print(f"Building SQLite from {src} ...")
conn = sqlite3.connect(dst)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=OFF")
conn.execute("PRAGMA cache_size=200000")
cur  = conn.cursor()

cur.execute("""
CREATE TABLE prices (
    oe           TEXT NOT NULL,
    price_eur    REAL NOT NULL,
    manufacturer TEXT,
    source       TEXT
)
""")

t0 = time.monotonic()
batch, total, skipped = [], 0, 0
BATCH = 50_000

with open(src, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            price = float(row['price_eur'])
        except (ValueError, KeyError):
            skipped += 1
            continue
        batch.append((row['oe'], price, row.get('manufacturer',''), row.get('source','')))
        total += 1
        if len(batch) >= BATCH:
            cur.executemany("INSERT INTO prices VALUES (?,?,?,?)", batch)
            batch.clear()
        if total % 500_000 == 0:
            elapsed = time.monotonic() - t0
            print(f"  {total:,} rows inserted ... {elapsed:.0f}s")

if batch:
    cur.executemany("INSERT INTO prices VALUES (?,?,?,?)", batch)

conn.commit()
elapsed = time.monotonic() - t0
print(f"\nInserted {total:,} rows ({skipped} skipped) in {elapsed:.1f}s")
print("Building index on oe ...")
cur.execute("CREATE INDEX idx_oe ON prices(oe)")
conn.commit()
conn.close()

size_mb = os.path.getsize(dst) / 1024**2
print(f"\nDone! auvika.db = {size_mb:.0f} MB")
print(f"Location: {dst}")
