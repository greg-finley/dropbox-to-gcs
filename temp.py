import os

import dropbox
from dotenv import load_dotenv

# TODO: Get rid of this
load_dotenv()

dbx = dropbox.Dropbox(os.getenv("DROPBOX_ACCESS_TOKEN"))

try:
    dropbox_file = dbx.files_list_folder("", recursive=True, include_media_info=True)
except dropbox.exceptions.AuthError as err:
    print(err.message)
