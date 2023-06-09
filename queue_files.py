import os
from time import sleep

import mysql.connector
import requests
from dotenv import load_dotenv
from google.cloud import pubsub_v1, secretmanager

load_dotenv()

DROPBOX_PREFIX = "/Users/gregoryfinley/Dropbox/"
CAMERA_UPLOADS_PREFIX = "/Users/gregoryfinley/Dropbox/Camera Uploads/"
DIRECTORY_PATH = "/Users/gregoryfinley/Dropbox"
BATCH_SIZE = int(os.getenv("BATCH_SIZE"), 20)
TOPIC_NAME = "projects/greg-finley/topics/dropbox-backup"
SECRET_NAME = "projects/greg-finley/secrets/DROPBOX_ACCESS_TOKEN"


def refresh_token() -> None:
    response = requests.post(
        "https://api.dropbox.com/oauth2/token",
        data={
            "refresh_token": os.environ["DROPBOX_REFRESH_TOKEN"],
            "grant_type": "refresh_token",
            "client_id": os.environ["DROPBOX_CLIENT_ID"],
            "client_secret": os.environ["DROPBOX_CLIENT_SECRET"],
        },
    )
    response.raise_for_status()
    token = response.json()["access_token"]

    secret_client = secretmanager.SecretManagerServiceClient()
    # Add a new version
    secret_version = secret_client.add_secret_version(
        request={
            "payload": {"data": token.encode("utf-8")},
            "parent": SECRET_NAME,
        }
    )
    secret_version_number: int = int(secret_version.name.split("/")[-1])
    # Delete the old version
    secret_client.destroy_secret_version(
        request={
            "name": f"{SECRET_NAME}/versions/{secret_version_number - 1}",
        }
    )


def queue_files_for_download():
    # Find all files we have locally
    file_list = build_file_list(DIRECTORY_PATH)
    print(f"Found {len(file_list)} files locally")

    # Get the list of files we have already processed
    mysql_connection = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USERNAME"),
        passwd=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
        ssl_ca=os.environ.get("SSL_CERT_FILE", "/etc/ssl/certs/ca-certificates.crt"),
    )
    mysql_connection.autocommit = True
    publisher = pubsub_v1.PublisherClient()
    query = "SELECT desktop_path FROM dropbox"
    cursor = mysql_connection.cursor()
    cursor.execute(query)
    existing_files = {DROPBOX_PREFIX + row[0] for row in cursor.fetchall()}
    cursor.close()
    # Wife sometimes moves files out of the Camera Uploads folder, so check for exact name matches
    camera_uploads_filenames = {
        f.split("/")[-1] for f in existing_files if f.startswith(CAMERA_UPLOADS_PREFIX)
    }

    missing_files = [
        file
        for file in file_list
        if file not in existing_files
        and file.split("/")[-1] not in camera_uploads_filenames
    ]
    if not missing_files:
        print("No files to queue for download")
        return

    refresh_token()
    futures = []
    for i, file in enumerate(missing_files):
        future = publisher.publish(
            TOPIC_NAME, file.removeprefix(DROPBOX_PREFIX).encode("utf-8")
        )
        print(file)
        futures.append(future)
        if i != 0 and i % BATCH_SIZE == 0:
            print(f"Queued {i} files for download")
            for future in futures:
                future.result()
            futures = []
            sleep(1)

    for future in futures:
        future.result()

    print(f"Queued {len(futures)} files for download")


def build_file_list(directory_path):
    file_list = []
    for filename in os.listdir(directory_path):
        file_path = os.path.join(directory_path, filename)
        if os.path.isdir(file_path):
            file_list.extend(build_file_list(file_path))
        elif not file_path.endswith(".DS_Store") and not file_path.endswith(".dropbox"):
            file_list.append(file_path)

    return file_list


if __name__ == "__main__":
    queue_files_for_download()
