import os

import dropbox
import mysql.connector
import requests
from google.cloud import pubsub_v1, secretmanager

ACCESS_TOKEN_SECRET_NAME = "projects/greg-finley/secrets/DROPBOX_ACCESS_TOKEN"
CURSOR_SECRET_NAME = "projects/greg-finley/secrets/DROPBOX_CURSOR"
TOPIC_NAME = "projects/greg-finley/topics/dropbox-backup"
secret_client = secretmanager.SecretManagerServiceClient()


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
    try:
        result = dbx.files_list_folder_continue(cursor=os.getenv("DROPBOX_CURSOR"))
    except dropbox.exceptions.AuthError:
        token = refresh_token()
        os.environ["DROPBOX_ACCESS_TOKEN"] = token
        dbx = dropbox.Dropbox(token)
        result = dbx.files_list_folder_continue(cursor=os.getenv("DROPBOX_CURSOR"))

    entries.extend(result.entries)
    while result.has_more:
        result = dbx.files_list_folder_continue(cursor=result.cursor)
        entries.extend(result.entries)

    if not entries:
        print("No new files found")
        return

    mysql_connection = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USERNAME"),
        passwd=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
        ssl_ca=os.environ.get("SSL_CERT_FILE", "/etc/ssl/certs/ca-certificates.crt"),
    )
    mysql_connection.autocommit = True
    publisher = pubsub_v1.PublisherClient()

    futures = []
    for entry in entries:
        if isinstance(entry, dropbox.files.FileMetadata):
            print(f"Queueing {entry.path_display}")
            query = """
            INSERT INTO dropbox (desktop_path, filename, status)
            VALUES (%s, SUBSTRING_INDEX(%s, '/', -1), 'pending')
            """
            cursor = mysql_connection.cursor()
            try:
                cursor.execute(query, (entry.path_display, entry.path_display))
            # Maybe we already enqueued this file
            except mysql.connector.Error as err:
                print(f"Failed to insert entry: {err}")
                continue
            finally:
                cursor.close()
            future = publisher.publish(TOPIC_NAME, entry.path_display.encode("utf-8"))
            futures.append(future)
        # TODO: Handle deletes and handle moving from "Camera Uploads"

    for future in futures:
        future.result()
    set_cursor_secret(result.cursor)


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

    # Add a new version
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


def set_cursor_secret(cursor):
    secret_version = secret_client.add_secret_version(
        request={
            "payload": {"data": cursor.encode("utf-8")},
            "parent": CURSOR_SECRET_NAME,
        }
    )
    secret_version_number: int = int(secret_version.name.split("/")[-1])
    # Delete the old version
    secret_client.destroy_secret_version(
        request={
            "name": f"{CURSOR_SECRET_NAME}/versions/{secret_version_number - 1}",
        }
    )
