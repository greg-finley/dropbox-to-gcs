import os

import dropbox
import requests
from google.cloud import secretmanager

SECRET_NAME = "projects/greg-finley/secrets/DROPBOX_ACCESS_TOKEN"


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
    try:
        thing = dbx.files_list_folder_continue(cursor=os.getenv("DROPBOX_CURSOR"))
    except dropbox.exceptions.AuthError as err:
        refresh_token()
        thing = dbx.files_list_folder_continue(cursor=os.getenv("DROPBOX_CURSOR"))
    print(thing)


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
