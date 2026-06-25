"""
Recovery script: extracts every source file from the initial git commit (88b9d2d),
strips null bytes, and writes clean versions to the working directory.
Run from the workflow-pro folder: python fix_all_files.py
"""
import subprocess, os, sys

INITIAL_COMMIT = "88b9d2d"

# Get list of all files in that commit
result = subprocess.run(
    ["git", "ls-tree", "-r", "--name-only", INITIAL_COMMIT],
    capture_output=True
)
if result.returncode != 0:
    print("ERROR: Could not list files from initial commit.")
    print(result.stderr.decode(errors='replace'))
    sys.exit(1)

files = result.stdout.decode(errors='replace').strip().splitlines()
print(f"Found {len(files)} files in commit {INITIAL_COMMIT}")

fixed = 0
skipped = 0

for filepath in files:
    # Only process source/config files
    ext = os.path.splitext(filepath)[1]
    if ext not in ('.js', '.jsx', '.ts', '.tsx', '.json', '.css', '.html', '.md'):
        skipped += 1
        continue

    # Get raw content (with null bytes) from git
    blob = subprocess.run(
        ["git", "show", f"{INITIAL_COMMIT}:{filepath}"],
        capture_output=True
    )
    if blob.returncode != 0:
        print(f"  SKIP (git error): {filepath}")
        skipped += 1
        continue

    raw = blob.stdout
    null_count = raw.count(b'\x00')
    clean = raw.replace(b'\x00', b'')

    if null_count == 0 and len(clean) < 10:
        print(f"  SKIP (empty): {filepath}")
        skipped += 1
        continue

    # Write clean content
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
    with open(filepath, 'wb') as f:
        f.write(clean)

    status = f"({null_count} nulls stripped)" if null_count > 0 else "(no nulls)"
    print(f"  OK {status}: {filepath}")
    fixed += 1

print(f"\nDone: {fixed} files fixed, {skipped} skipped.")
print("\nNext: git add -A && git commit -m 'Restore complete source files from initial commit' && git push origin main")
