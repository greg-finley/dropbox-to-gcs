import os

import psycopg

conn = psycopg.connect(os.environ["NEON_DATABASE_URL"])
conn.autocommit = True

query = """
            INSERT INTO dropbox (desktop_path, filename, status)
            VALUES (%s, SPLIT_PART(%s, '/', -1), 'pending')
            """

clean_name = "Camera Uploads/2024-04-14 17.13.46.mov"
with conn.cursor() as cursor:
    try:
        cursor.execute(query, (clean_name, clean_name))
        print(f"Queued {clean_name}")
    except psycopg.errors.UniqueViolation as err:
        print("Already queued")
