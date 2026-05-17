import base64
import os

import dropbox
import psycopg
from google.cloud import secretmanager, storage

secret_client = secretmanager.SecretManagerServiceClient()
gcs_client = storage.Client()
gcs_bucket = gcs_client.get_bucket("greg-finley-dropbox-backup")


def get_db_connection():
    conn = psycopg.connect(os.environ["NEON_DATABASE_URL"])
    conn.autocommit = True
    return conn


def run(event, context):
    filename = base64.b64decode(event["data"]).decode("utf-8")
    try:
        main(filename)
    except Exception as e:
        update_status(filename, "failed")
        raise e


def main(filename):
    dropbox_access_token = secret_client.access_secret_version(
        name="projects/greg-finley/secrets/DROPBOX_ACCESS_TOKEN/versions/latest"
    ).payload.data.decode("utf-8")
    dbx = dropbox.Dropbox(dropbox_access_token)
    print(f"Processing {filename}...")
    dropbox_file = dbx.files_download("/" + filename)
    content_hash = dropbox_file[0].content_hash
    content_type = dropbox_file[1].headers.get("Content-Type")
    gcs_file = gcs_bucket.blob(filename)
    gcs_file.upload_from_string(
        dropbox_file[1].content, content_type=content_type, timeout=400
    )
    update_status(filename, "done", content_hash)
    print(f"Uploaded {filename} - {content_type}")


def update_status(filename, status, content_hash=None):
    query = """
    INSERT INTO dropbox (desktop_path, filename, status, content_hash)
    VALUES (%s, SPLIT_PART(%s, '/', -1), %s, %s)
    ON CONFLICT (desktop_path) DO UPDATE SET status = %s, content_hash = %s
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (filename, filename, status, content_hash, status, content_hash))
