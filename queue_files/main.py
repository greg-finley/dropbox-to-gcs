import os
from time import sleep

import dropbox
import mysql.connector
import requests
from google.cloud import pubsub_v1, secretmanager, storage

ACCESS_TOKEN_SECRET_NAME = "projects/greg-finley/secrets/DROPBOX_ACCESS_TOKEN"
TOPIC_NAME = "projects/greg-finley/topics/dropbox-backup"
secret_client = secretmanager.SecretManagerServiceClient()

mysql_connection = mysql.connector.connect(
    host=os.getenv("MYSQL_HOST"),
    user=os.getenv("MYSQL_USERNAME"),
    passwd=os.getenv("MYSQL_PASSWORD"),
    database=os.getenv("MYSQL_DATABASE"),
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
    entries = []
    dbx = dropbox.Dropbox(os.getenv("DROPBOX_ACCESS_TOKEN"))
    query = "SELECT dropbox_cursor FROM dropbox_cursor_table"
    cursor = mysql_connection.cursor()
    cursor.execute(query)
    old_cursor = cursor.fetchone()[0]
    cursor.close()

    try:
        dropbox_result = dbx.files_list_folder_continue(cursor=old_cursor)
    except dropbox.exceptions.AuthError:
        token = refresh_token()
        os.environ["DROPBOX_ACCESS_TOKEN"] = token
        dbx = dropbox.Dropbox(token)
        dropbox_result = dbx.files_list_folder_continue(cursor=old_cursor)

    entries.extend(dropbox_result.entries)
    while dropbox_result.has_more:
        dropbox_result = dbx.files_list_folder_continue(cursor=dropbox_result.cursor)
        entries.extend(dropbox_result.entries)

    if not entries:
        print("No new files found")
        return

    publisher = pubsub_v1.PublisherClient()
    gcs_client = storage.Client()
    gcs_bucket = gcs_client.get_bucket("greg-finley-dropbox-backup")

    futures = []
    for i, entry in enumerate(entries):
        # Every third item, sleep a bit
        if i % 3 == 0:
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
    if dropbox_result.cursor != old_cursor:
        query = "UPDATE dropbox_cursor_table SET dropbox_cursor = %s"
        cursor = mysql_connection.cursor()
        cursor.execute(query, (dropbox_result.cursor,))
        cursor.close()


def refresh_token():
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
