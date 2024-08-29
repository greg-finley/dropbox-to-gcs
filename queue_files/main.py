import json
import os

import dropbox
import psycopg
import requests
from google.cloud import pubsub_v1, secretmanager, storage

ACCESS_TOKEN_SECRET_NAME = "projects/greg-finley/secrets/DROPBOX_ACCESS_TOKEN"
TOPIC_NAME = "projects/greg-finley/topics/dropbox-backup"
QUEUE_TOPIC_NAME = "projects/greg-finley/topics/dropbox-queue-files"
secret_client = secretmanager.SecretManagerServiceClient()


def run(event, context):
    dbx = dropbox.Dropbox(os.getenv("DROPBOX_ACCESS_TOKEN"))
    query = (
        "SELECT dropbox_cursor from dropbox_cursors order by created_at desc limit 1"
    )
    conn = psycopg.connect(os.environ["NEON_DATABASE_URL"])
    conn.autocommit = True
    with conn.cursor() as cursor:
        cursor.execute(query)
        old_cursor = cursor.fetchone()[0]
        print("Old cursor: ", old_cursor)

    try:
        dropbox_result = dbx.files_list_folder_continue(cursor=old_cursor)
    except dropbox.exceptions.AuthError:
        token = refresh_token()
        os.environ["DROPBOX_ACCESS_TOKEN"] = token
        dbx = dropbox.Dropbox(token)
        dropbox_result = dbx.files_list_folder_continue(cursor=old_cursor)

    # Immediately write the new cursor to the database so further requests use
    # it and cut down on duplicated work
    print("New cursor: ", dropbox_result.cursor)
    query = "INSERT INTO dropbox_cursors (dropbox_cursor) VALUES (%s) ON CONFLICT (dropbox_cursor) DO NOTHING"
    with conn.cursor() as cursor:
        cursor.execute(query, (dropbox_result.cursor,))

    publisher = pubsub_v1.PublisherClient()
    gcs_client = storage.Client()
    gcs_bucket = gcs_client.get_bucket("greg-finley-dropbox-backup")

    futures = []
    for entry in dropbox_result.entries:
        print(entry)
        clean_name = entry.path_display.removeprefix("/")
        if isinstance(entry, dropbox.files.FileMetadata):
            print(f"Queueing {clean_name}")
            query = """
            INSERT INTO dropbox (desktop_path, filename, status)
            VALUES (%s, SPLIT_PART(%s, '/', -1), 'pending')
            """
            with conn.cursor() as cursor:
                try:
                    cursor.execute(query, (clean_name, clean_name))
                except psycopg.errors.UniqueViolation as err:
                    print(f"Already queued {clean_name}")
                    continue

            print(f"Queued {clean_name}")
            future = publisher.publish(TOPIC_NAME, clean_name.encode("utf-8"))
            futures.append(future)
        elif isinstance(entry, dropbox.files.DeletedMetadata):
            print(f"Deleting {clean_name}")
            query = "UPDATE dropbox SET status = 'deleted' WHERE desktop_path = %s"
            with conn.cursor() as cursor:
                cursor.execute(query, (clean_name,))

            try:
                gcs_bucket.delete_blob(clean_name)
            except Exception as err:
                print(f"Failed to delete {clean_name}: {err}")

    # also reenque all failed files
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, desktop_path 
            FROM dropbox 
            WHERE status = 'failed'
            FOR UPDATE SKIP LOCKED
            """
        )
        failed_entries = cursor.fetchall()

        if failed_entries:
            for entry_id, clean_name in failed_entries:
                future = publisher.publish(TOPIC_NAME, clean_name.encode("utf-8"))
                futures.append(future)
                cursor.execute(
                    "UPDATE dropbox SET status = 'pending' WHERE id = %s", (entry_id,)
                )
                print(f"Re-queued {clean_name}")

    for future in futures:
        future.result()

    # Trigger the job again if there are more files to process
    if dropbox_result.has_more:
        publisher.publish(QUEUE_TOPIC_NAME, "Hi".encode("utf-8"))

    conn.close()


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
