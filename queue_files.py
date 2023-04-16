import os

import mysql.connector
from dotenv import load_dotenv
from google.cloud import pubsub_v1

load_dotenv()

DROPBOX_PREFIX = "/Users/gregoryfinley/Dropbox/"
DIRECTORY_PATH = "/Users/gregoryfinley/Dropbox/Greg Stuff"
NUM_FILES = int(os.getenv("NUM_FILES"))
TOPIC_NAME = "projects/greg-finley/topics/dropbox-backup"


def queue_files_for_download():
    # Find all files we have locally
    file_list = build_file_list(DIRECTORY_PATH)

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

    missing_files = [file for file in file_list if file not in existing_files]
    futures = []
    for file in missing_files[:NUM_FILES]:
        future = publisher.publish(
            TOPIC_NAME, file.removeprefix(DROPBOX_PREFIX).encode("utf-8")
        )
        futures.append(future)

    for future in futures:
        future.result()


def build_file_list(directory_path):
    file_list = []
    for filename in os.listdir(directory_path):
        file_path = os.path.join(directory_path, filename)
        if os.path.isdir(file_path):
            file_list.extend(build_file_list(file_path))
        elif not file_path.endswith(".DS_Store"):
            file_list.append(file_path)

    return file_list


if __name__ == "__main__":
    queue_files_for_download()