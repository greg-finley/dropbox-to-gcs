import csv
import os
from collections import defaultdict

import dropbox
from dotenv import load_dotenv

load_dotenv("../.env", override=True)

PHOTO_VIDEO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".mov"}
DUPES_FILE = "dupes.csv"


def is_photo_or_video(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return f".{ext}" in PHOTO_VIDEO_EXTENSIONS


def main():
    dbx = dropbox.Dropbox(os.environ["DROPBOX_ACCESS_TOKEN"])

    groups = defaultdict(set)
    with open(DUPES_FILE) as f:
        for row in csv.DictReader(f):
            if is_photo_or_video(row["filename"]):
                groups[row["content_hash"]].add(row["desktop_path"])

    for content_hash, paths in sorted(groups.items()):
        paths = sorted(paths)
        keep, *delete = paths
        print(f"SAVING   {content_hash}  {keep}")
        for path in delete:
            print(f"DELETING {content_hash}  {path}")
            try:
                dbx.files_delete_v2("/" + path)
            except dropbox.exceptions.ApiError as e:
                if "not_found" in str(e):
                    print(f"  (already gone, skipping)")
                else:
                    raise


if __name__ == "__main__":
    main()
