import os

import dropbox
import MySQLdb
from dotenv import load_dotenv
from google.cloud import storage

load_dotenv()

dbx = dropbox.Dropbox(os.getenv("ACCESS_TOKEN"))
gcs_client = storage.Client()
gcs_bucket = gcs_client.get_bucket("greg-finley-dropbox-backup")
# directory_path = "/Users/gregoryfinley/Dropbox"
directory_path = (
    "/Users/gregoryfinley/Dropbox/Greg Stuff/Greg Documents/CHICO STATE/Junior"
)
mysql_connection = MySQLdb.connect(
    host=os.getenv("MYSQL_HOST"),
    user=os.getenv("MYSQL_USERNAME"),
    passwd=os.getenv("MYSQL_PASSWORD"),
    db=os.getenv("MYSQL_DATABASE"),
    ssl_mode="VERIFY_IDENTITY",
    ssl={"ca": os.environ.get("SSL_CERT_FILE", "/etc/ssl/certs/ca-certificates.crt")},
)
mysql_connection.autocommit(True)


def process_files_recursively(directory_path):
    query = "SELECT desktop_path FROM dropbox"
    mysql_connection.query(query)
    r = mysql_connection.store_result()
    existing_files = [row["desktop_path"] for row in r.fetch_row(maxrows=0, how=1)]
    file_count = 0
    for filename in os.listdir(directory_path):
        file_path = os.path.join(directory_path, filename)
        if os.path.isdir(file_path):
            subdirectory_file_count = process_files_recursively(file_path)
            file_count += subdirectory_file_count
        else:
            clean_file_path = file_path.removeprefix("/Users/gregoryfinley/Dropbox/")
            if clean_file_path in existing_files or clean_file_path.endswith(
                ".DS_Store"
            ):
                print(f"Skipping {clean_file_path}")
                continue
            print(f"Uploading {clean_file_path}...")
            dropbox_file = dbx.files_download("/" + clean_file_path)
            content_type = dropbox_file[1].headers.get("Content-Type")
            gcs_file = gcs_bucket.blob(clean_file_path)
            gcs_file.upload_from_string(
                dropbox_file[1].content, content_type=content_type
            )
            query = "INSERT INTO dropbox (desktop_path) VALUES (%s)"
            mysql_connection.cursor().execute(query, (clean_file_path,))

            print(f"Uploaded {clean_file_path} - {content_type}")
            file_count += 1
    return file_count


try:
    total_file_count = process_files_recursively(directory_path)
    print(f"Total files: {total_file_count}")
finally:
    mysql_connection.close()
