import os

import dropbox
import psycopg
from dotenv import load_dotenv

load_dotenv("../.env", override=True)

CHUNK_SIZE = 500


def list_all_files(dbx):
    """Walk all of Dropbox recursively, yielding (path_lower, content_hash) tuples."""
    result = dbx.files_list_folder("", recursive=True)
    page = 0
    total = 0
    while True:
        page += 1
        batch = [
            (entry.path_lower.lstrip("/"), entry.content_hash)
            for entry in result.entries
            if isinstance(entry, dropbox.files.FileMetadata) and entry.content_hash
        ]
        total += len(batch)
        print(f"  Page {page}: {len(result.entries)} entries, {total:,} files collected so far")
        yield from batch
        if not result.has_more:
            break
        result = dbx.files_list_folder_continue(result.cursor)


def update_chunk(cursor, chunk):
    cases = "\n  ".join(
        f"WHEN LOWER(desktop_path) = {psycopg.sql.quote(path)} THEN {psycopg.sql.quote(content_hash)}"
        for path, content_hash in chunk
    )
    in_list = ", ".join(psycopg.sql.quote(path) for path, _ in chunk)
    sql = f"""
UPDATE dropbox
SET content_hash = CASE
  {cases}
END
WHERE LOWER(desktop_path) IN ({in_list})
  AND content_hash IS NULL
"""
    cursor.execute(sql)
    return cursor.rowcount


HASHES_FILE = "hashes.tsv"


def fetch(dbx):
    print("Listing all Dropbox files (this may take a few minutes)...")
    pairs = list(list_all_files(dbx))
    print(f"Found {len(pairs):,} files with content_hash in Dropbox")
    with open(HASHES_FILE, "w") as f:
        for path, content_hash in pairs:
            f.write(f"{path}\t{content_hash}\n")
    print(f"Written to {HASHES_FILE}")


def to_mojibake(pairs):
    result = []
    for path, content_hash in pairs:
        try:
            mojibake_path = path.encode("utf-8").decode("latin-1")
            if mojibake_path != path:
                result.append((mojibake_path, content_hash))
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return result


def run_update(conn, pairs, label):
    total_updated = 0
    for i in range(0, len(pairs), CHUNK_SIZE):
        chunk = pairs[i : i + CHUNK_SIZE]
        with conn.cursor() as cur:
            total_updated += update_chunk(cur, chunk)
        print(f"  [{label}] Processed {min(i + CHUNK_SIZE, len(pairs)):,}/{len(pairs):,} — updated {total_updated:,} rows so far")
    return total_updated


def update(db_url):
    with open(HASHES_FILE) as f:
        pairs = [line.rstrip("\n").split("\t") for line in f]
    print(f"Loaded {len(pairs):,} pairs from {HASHES_FILE}")

    mojibake_pairs = to_mojibake(pairs)
    print(f"{len(mojibake_pairs):,} paths have non-ASCII characters — will retry as mojibake")

    conn = psycopg.connect(db_url)
    conn.autocommit = True

    total = run_update(conn, pairs, "unicode")
    total += run_update(conn, mojibake_pairs, "mojibake")

    conn.close()
    print(f"\nDone. Updated {total:,} rows total.")


def main():
    token = os.environ["DROPBOX_ACCESS_TOKEN"]
    db_url = os.environ["NEON_DATABASE_URL"]
    dbx = dropbox.Dropbox(token)
    fetch(dbx)
    update(db_url)


def sample():
    token = os.environ["DROPBOX_ACCESS_TOKEN"]
    dbx = dropbox.Dropbox(token)
    result = dbx.files_list_folder("", recursive=True)
    for entry in result.entries:
        if isinstance(entry, dropbox.files.FileMetadata):
            print(entry.path_lower.lstrip("/"))


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "fetch":
        fetch(dropbox.Dropbox(os.environ["DROPBOX_ACCESS_TOKEN"]))
    elif cmd == "update":
        update(os.environ["NEON_DATABASE_URL"])
    elif cmd == "sample":
        sample()
    else:
        main()
