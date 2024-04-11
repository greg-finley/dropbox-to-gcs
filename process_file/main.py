import base64
import os

import dropbox
import psycopg
from google.cloud import secretmanager, storage

gcs_client = storage.Client()
gcs_bucket = gcs_client.get_bucket("greg-finley-dropbox-backup")
secret_client = secretmanager.SecretManagerServiceClient()


def run(event, context):
    dropbox_access_token = secret_client.access_secret_version(
        name="projects/greg-finley/secrets/DROPBOX_ACCESS_TOKEN/versions/latest"
    ).payload.data.decode("utf-8")
    dbx = dropbox.Dropbox(dropbox_access_token)
    filename = base64.b64decode(event["data"]).decode("utf-8")
    print(f"Processing {filename}...")
    dropbox_file = dbx.files_download("/" + filename)
    content_type = dropbox_file[1].headers.get("Content-Type")
    gcs_file = gcs_bucket.blob(filename)
    gcs_file.upload_from_string(
        dropbox_file[1].content, content_type=content_type, timeout=400
    )
    query = """
    INSERT INTO dropbox (desktop_path, filename, status)
    VALUES (%s, SUBSTRING_INDEX(%s, '/', -1), 'done')
    ON DUPLICATE KEY UPDATE status = 'done'
    """
    with psycopg.connect(os.environ["NEON_DATABASE_URL"]) as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (filename, filename))
    print(f"Uploaded {filename} - {content_type}")
