import json
import os
from time import sleep

import dropbox
import mysql.connector
import requests
from google.cloud import pubsub_v1, secretmanager, storage

ACCESS_TOKEN_SECRET_NAME = "projects/greg-finley/secrets/DROPBOX_ACCESS_TOKEN"
TOPIC_NAME = "projects/greg-finley/topics/dropbox-backup"
QUEUE_TOPIC_NAME = "projects/greg-finley/topics/dropbox-queue-files"
secret_client = secretmanager.SecretManagerServiceClient()

mysql_config = json.loads(os.environ["MYSQL_CONFIG"])

mysql_connection = mysql.connector.connect(
    host=mysql_config["MYSQL_HOST"],
    user=mysql_config["MYSQL_USERNAME"],
    passwd=mysql_config["MYSQL_PASSWORD"],
    database=mysql_config["MYSQL_DATABASE"],
    ssl_ca=os.environ.get("SSL_CERT_FILE", "/etc/ssl/certs/ca-certificates.crt"),
)
mysql_connection.autocommit = True


def run(event, context):
    """Responds to any HTTP request.
    Args:
        request (flask.Request): HTTP request object.
    Returns:
        The response text or any set of values that can be turned into a
        Response object using
        `make_response <http://flask.pocoo.org/docs/1.0/api/#flask.Flask.make_response>`.
    """
    dbx = dropbox.Dropbox(os.getenv("DROPBOX_ACCESS_TOKEN"))
    query = (
        "SELECT dropbox_cursor from dropbox_cursors order by created_at desc limit 1"
    )
    cursor = mysql_connection.cursor()
    cursor.execute(query)
    old_cursor = cursor.fetchone()[0]
    print("Old cursor type: ", type(old_cursor))
    cursor.close()

    try:
        dropbox_result = dbx.files_list_folder_continue(cursor=old_cursor)
    except dropbox.exceptions.AuthError:
        token = refresh_token()
        os.environ["DROPBOX_ACCESS_TOKEN"] = token
        dbx = dropbox.Dropbox(token)
        dropbox_result = dbx.files_list_folder_continue(cursor=old_cursor)

    # Immediately write the new cursor to the database so further requests use
    # it and cut down on duplicated work
    query = "INSERT IGNORE INTO dropbox_cursors (dropbox_cursor) VALUES (%s)"
    cursor = mysql_connection.cursor()
    cursor.execute(query, (dropbox_result.cursor,))
    cursor.close()

    if not dropbox_result.entries:
        print("No new files found")
        return

    publisher = pubsub_v1.PublisherClient()
    gcs_client = storage.Client()
    gcs_bucket = gcs_client.get_bucket("greg-finley-dropbox-backup")

    futures = []
    for i, entry in enumerate(dropbox_result.entries):
        # Every third item, sleep a bit
        if i % 3 == 0 and i != 0:
            sleep(1)
        clean_name = entry.path_display.removeprefix("/")
        if isinstance(entry, dropbox.files.FileMetadata):
            print(f"Queueing {clean_name}")
            query = """
            INSERT INTO dropbox (desktop_path, filename, status)
            VALUES (%s, SUBSTRING_INDEX(%s, '/', -1), 'pending')
            """
            cursor = mysql_connection.cursor()
            try:
                cursor.execute(query, (clean_name, clean_name))
                print(f"Queued {clean_name}")
                cursor.close()
            # Maybe we already enqueued this file; continue instead of enqueueing again
            except mysql.connector.Error as err:
                print(f"Failed to insert entry: {err}")
                cursor.close()
                continue
            future = publisher.publish(TOPIC_NAME, clean_name.encode("utf-8"))
            futures.append(future)
        elif isinstance(entry, dropbox.files.DeletedMetadata):
            print(f"Deleting {clean_name}")
            query = "UPDATE dropbox SET status = 'deleted' WHERE desktop_path = %s"
            cursor = mysql_connection.cursor()
            cursor.execute(query, (clean_name,))
            cursor.close()
            try:
                gcs_bucket.delete_blob(clean_name)
            except Exception as err:
                print(f"Failed to delete {clean_name}: {err}")

    for future in futures:
        future.result()

    # Trigger the job again if there are more files to process
    if dropbox_result.has_more:
        publisher.publish(QUEUE_TOPIC_NAME, "Hi".encode("utf-8"))


def refresh_token():
    dropbox_config = json.loads(os.environ["DROPBOX_CONFIG"])
    response = requests.post(
        "https://api.dropbox.com/oauth2/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": dropbox_config["DROPBOX_REFRESH_TOKEN"],
            "client_id": dropbox_config["DROPBOX_CLIENT_ID"],
            "client_secret": dropbox_config["DROPBOX_CLIENT_SECRET"],
        },
    )
    response.raise_for_status()
    token = response.json()["access_token"]

    secret_version = secret_client.add_secret_version(
        request={
            "payload": {"data": token.encode("utf-8")},
            "parent": ACCESS_TOKEN_SECRET_NAME,
        }
    )
    secret_version_number: int = int(secret_version.name.split("/")[-1])
    # Delete the old version
    secret_client.destroy_secret_version(
        request={
            "name": f"{ACCESS_TOKEN_SECRET_NAME}/versions/{secret_version_number - 1}",
        }
    )
    return token
