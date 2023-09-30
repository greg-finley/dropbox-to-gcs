# dropbox-to-gcs

Back up my whole Dropbox to Google Cloud Storage using Dropbox webhooks.

## Why?

Some existential worry that Dropbox could blow up someday, but also it's [relatively cheap](https://cloud.google.com/storage/pricing#price-tables) to store data in the Archive storage class (I have about 400 GB, so should be about $0.48/month).

## Prerequisites

Make a [Dropbox app](https://www.dropbox.com/developers/apps). You will only need to process your own files, so it can stay in Development status.

## Functions

This process is split into three Google Cloud Functions, each with a folder in the repo root:

1. `webhook` -- respond to Dropbox webhook. In your Dropbox app, set the webhook URL to the URL of this function.
2. `queue_files` -- triggered by the previous job. Figure out the last cursor. Directly delete any files that have been deleted from Dropbox. For new files, queue them to the new job.
3. `process_file` -- download the file from Dropbox and upload it to GCS.
4. `deploy_requeue_failed_files` -- can be manually triggered to requeue files that failed to process.
