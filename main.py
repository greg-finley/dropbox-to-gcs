import os

import dropbox
from dotenv import load_dotenv
from google.cloud import storage

load_dotenv()

# Initialize Dropbox client
dbx = dropbox.Dropbox(os.getenv("ACCESS_TOKEN"))

file_count = 0


def list_files(dbx, path="", cursor=None):
    global file_count
    # List files in the current folder
    if cursor is None:
        result = dbx.files_list_folder(path)
    else:
        result = dbx.files_list_folder_continue(cursor)

    # Print each file name and update file count
    for entry in result.entries:
        # if isinstance(entry, dropbox.files.FileMetadata):
        #     print(entry.path_lower)
        #     file_count += 1

        # Recursively list files in subfolders
        if isinstance(entry, dropbox.files.FolderMetadata):
            print(entry.path_lower)
            list_files(dbx, entry.path_display, None)

    # Repeat the process if there are more files
    if result.has_more:
        list_files(dbx, path, result.cursor)


# List all files in Dropbox and count them
try:
    list_files(dbx)
finally:
    print(f"Total number of files (excluding folders): {file_count}")
