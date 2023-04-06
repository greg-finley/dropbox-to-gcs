import os

import dropbox
import mysql.connector
from dotenv import load_dotenv
from google.cloud import storage

load_dotenv()

dbx = dropbox.Dropbox(os.getenv("ACCESS_TOKEN"))
gcs_client = storage.Client()
gcs_bucket = gcs_client.get_bucket("greg-finley-dropbox-backup")
gcs_bucket_file_list = gcs_client.get_bucket("greg-finley-dropbox-file-list")
mysql_connection = mysql.connector.connect(
    host=os.getenv("MYSQL_HOST"),
    user=os.getenv("MYSQL_USERNAME"),
    passwd=os.getenv("MYSQL_PASSWORD"),
    database=os.getenv("MYSQL_DATABASE"),
    ssl_ca=os.environ.get("SSL_CERT_FILE", "/etc/ssl/certs/ca-certificates.crt"),
)
cursor = mysql_connection.cursor()


def process_files_recursively(file_list):
    query = "SELECT desktop_path FROM dropbox"
    cursor.execute(query)
    existing_files = [row[0] for row in cursor.fetchall()]
    file_count = 0
    for filename in file_list:
        clean_file_path = filename.removeprefix("/Users/gregoryfinley/Dropbox/")
        if clean_file_path in existing_files or clean_file_path.endswith(".DS_Store"):
            print(f"Skipping {clean_file_path}")
            continue
        print(f"Uploading {clean_file_path}...")
        dropbox_file = dbx.files_download("/" + clean_file_path)
        content_type = dropbox_file[1].headers.get("Content-Type")
        gcs_file = gcs_bucket.blob(clean_file_path)
        gcs_file.upload_from_string(dropbox_file[1].content, content_type=content_type)
        query = "INSERT INTO dropbox (desktop_path) VALUES (%s)"
        cursor.execute(query, (clean_file_path,))
        mysql_connection.commit()
        print(f"Uploaded {clean_file_path} - {content_type}")
        file_count += 1
    return file_count


# Get file list from GCS
gcs_file = gcs_bucket_file_list.blob("file_list.txt")
file_list = gcs_file.download_as_string().decode("utf-8").splitlines()


try:
    total_file_count = process_files_recursively(file_list)
    print(f"Total files: {total_file_count}")
finally:
    cursor.close()
    mysql_connection.close()
