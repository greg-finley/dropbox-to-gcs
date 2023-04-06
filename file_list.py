import os

from google.cloud import storage

# directory_path = "/Users/gregoryfinley/Dropbox"
directory_path = "/Users/gregoryfinley/Dropbox/Greg Stuff/Greg Documents/GEORGE MASON"


def build_file_list(directory_path):
    file_list = []
    for filename in os.listdir(directory_path):
        file_path = os.path.join(directory_path, filename)
        if os.path.isdir(file_path):
            file_list.extend(build_file_list(file_path))
        else:
            file_list.append(file_path)

    return file_list


file_list = build_file_list(directory_path)

# Write file list to GCS
gcs_client = storage.Client()
gcs_bucket = gcs_client.get_bucket("greg-finley-dropbox-file-list")
gcs_file = gcs_bucket.blob("file_list.txt")
gcs_file.upload_from_string("\n".join(file_list))
