import base64
import os

import dropbox
import mysql.connector
from google.cloud import storage

dbx = dropbox.Dropbox(os.getenv("DROPBOX_ACCESS_TOKEN"))
gcs_client = storage.Client()
gcs_bucket = gcs_client.get_bucket("greg-finley-dropbox-backup")
mysql_connection = mysql.connector.connect(
    host=os.getenv("MYSQL_HOST"),
    user=os.getenv("MYSQL_USERNAME"),
    passwd=os.getenv("MYSQL_PASSWORD"),
    database=os.getenv("MYSQL_DATABASE"),
    ssl_ca=os.environ.get("SSL_CERT_FILE", "/etc/ssl/certs/ca-certificates.crt"),
)
mysql_connection.autocommit = True


def run(event, context):
    filename = base64.b64decode(event["data"]).decode("utf-8")
    print(f"Processing {filename}...")
    dropbox_file = dbx.files_download("/" + filename)
    content_type = dropbox_file[1].headers.get("Content-Type")
    gcs_file = gcs_bucket.blob(filename)
    gcs_file.upload_from_string(dropbox_file[1].content, content_type=content_type)
    query = """INSERT INTO dropbox (desktop_path, status) VALUES (%s, 'done')
    ON DUPLICATE KEY UPDATE status = 'done'"""
    cursor = mysql_connection.cursor()
    cursor.execute(query, (filename,))
    cursor.close()
    print(f"Uploaded {filename} - {content_type}")
