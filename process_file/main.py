import base64
import json
import os

import dropbox
import mysql.connector
from google.cloud import secretmanager, storage

gcs_client = storage.Client()
gcs_bucket = gcs_client.get_bucket("greg-finley-dropbox-backup")
mysql_config_str = os.environ["MYSQL_CONFIG"]
mysql_config_dict = json.loads(mysql_config_str)
secret_client = secretmanager.SecretManagerServiceClient()
dropbox_access_token = secret_client.access_secret_version(
    name="projects/greg-finley/secrets/DROPBOX_ACCESS_TOKEN/versions/latest"
).payload.data.decode("utf-8")
dbx = dropbox.Dropbox(dropbox_access_token)


mysql_connection = mysql.connector.connect(
    host=mysql_config_dict["MYSQL_HOST"],
    port=mysql_config_dict["MYSQL_PORT"],
    user=mysql_config_dict["MYSQL_USERNAME"],
    passwd=mysql_config_dict["MYSQL_PASSWORD"],
    database=mysql_config_dict["MYSQL_DATABASE"],
)
mysql_connection.autocommit = True


def run(event, context):
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
    cursor = mysql_connection.cursor()
    cursor.execute(query, (filename, filename))
    cursor.close()
    print(f"Uploaded {filename} - {content_type}")
