import mimetypes
import os

import dropbox
from dotenv import load_dotenv
from google.cloud import storage

load_dotenv()

# Check MySql if file has been uploaded already


def print_files_recursively(directory_path):
    file_count = 0
    for filename in os.listdir(directory_path):
        file_path = os.path.join(directory_path, filename)
        if os.path.isdir(file_path):
            subdirectory_file_count = print_files_recursively(file_path)
            file_count += subdirectory_file_count
        else:
            content_type = (
                mimetypes.guess_type(file_path)[0] or "application/octet-stream"
            )
            print(
                f"{file_path.removeprefix('/Users/gregoryfinley/Dropbox/')} - {content_type}"
            )
            file_count += 1
    return file_count


directory_path = "/Users/gregoryfinley/Dropbox"
total_file_count = print_files_recursively(directory_path)
print(f"Total files: {total_file_count}")


# # Initialize Dropbox client
# dbx = dropbox.Dropbox(os.getenv("ACCESS_TOKEN"))

# has_more = True
# cursor = None
# num_files = 0

# while has_more:
#     if cursor is None:
#         result = dbx.files_list_folder(path="", recursive=True)
#     else:
#         result = dbx.files_list_folder_continue(cursor)

#     for entry in result.entries:
#         # Skip folders
#         if isinstance(entry, dropbox.files.FolderMetadata):
#             continue

#         # Skip deleted
#         if isinstance(entry, dropbox.files.DeletedMetadata):
#             continue

#         if not entry.path_lower.endswith(".pdf"):
#             continue

#         # if not entry.path_lower.endswith(".tiff"):
#         #     continue

#         # Print the file and its folder path
#         print(entry.path_lower)
#         dropbox_file = dbx.files_download(entry.path_display)
#         # Print the file content-type
#         content_type = dropbox_file[1].headers.get("Content-Type")

#         # Create a GCS client object
#         gcs_client = storage.Client()

#         # Get a reference to the GCS bucket
#         gcs_bucket = gcs_client.get_bucket("greg-finley-dropbox-backup")

#         # Upload the file to GCS
#         gcs_file = gcs_bucket.blob(entry.path_lower)
#         gcs_file.upload_from_string(dropbox_file[1].content, content_type=content_type)
#         num_files += 1

#     # Update cursor
#     cursor = result.cursor

#     # Repeat only if there's more to do
#     # has_more = result.has_more
#     has_more = False

# print("Total number of files: ", num_files)
