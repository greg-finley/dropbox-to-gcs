import json
import os
from time import sleep

import dropbox
import mysql.connector
import requests
from flask import Response
from google.cloud import pubsub_v1, secretmanager

TOPIC_NAME = "projects/greg-finley/topics/dropbox-backup"
ACCESS_TOKEN_SECRET_NAME = "projects/greg-finley/secrets/DROPBOX_ACCESS_TOKEN"

mysql_config = json.loads(os.environ["MYSQL_CONFIG"])

mysql_connection = mysql.connector.connect(
    unix_socket=mysql_config["MYSQL_SOCKET"],
    user=mysql_config["MYSQL_USERNAME"],
    passwd=mysql_config["MYSQL_PASSWORD"],
    database=mysql_config["MYSQL_DATABASE"],
)
mysql_connection.autocommit = True
secret_client = secretmanager.SecretManagerServiceClient()


def run(request):
    dbx = dropbox.Dropbox(os.getenv("DROPBOX_ACCESS_TOKEN"))

    try:
        dbx.files_list_folder("")
    except dropbox.exceptions.AuthError:
        refresh_token()

    query = "SELECT desktop_path from dropbox where status  = 'pending';"
    cursor = mysql_connection.cursor()
    cursor.execute(query)
    desktop_paths = [row[0] for row in cursor.fetchall()]
    cursor.close()

    publisher = pubsub_v1.PublisherClient()

    futures = []
    for i, path in enumerate(desktop_paths):
        print(path)
        # Every third item, sleep a bit
        if i % 3 == 0 and i != 0:
            sleep(1)
        future = publisher.publish(TOPIC_NAME, path.encode("utf-8"))
        futures.append(future)

    for future in futures:
        future.result()

    resp = Response("OK")
    resp.headers["Content-Type"] = "text/plain"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


# TODO: Make this shared between this job and the regular queueing job at some point
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
