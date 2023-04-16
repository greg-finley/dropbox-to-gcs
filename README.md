# dropbox-to-gcs

Back up my whole Dropbox to Google Cloud Storage.

## Why?

Some existential worry that Dropbox could blow up someday, but also it's [relatively cheap](https://cloud.google.com/storage/pricing#price-tables) to store data in the Archive storage class (I have about 400 GB, so should be about $0.48/month).

## Steps

Due to weirdness with the Dropbox API, this ended up as sort of a hodge-podge. The API to list all of your Dropbox files is extremely slow due to having to page through all the results, so I instead relied on the list of Dropbox files as they appear on the sync to my Mac.

1. Link your Dropbox file list [to your Mac or PC](https://www.dropbox.com/desktop). Dropbox will display all of your files in your computer's folder structure through placeholders, without actually taking up space on your hard drive.

2. Make a [Dropbox app](https://www.dropbox.com/developers/apps). You will only need to process your own files, so it can stay in Development status.

3. If you have not run this sync in a while, you will need to get a fresh API key.

Go to https://www.dropbox.com/oauth2/authorize?client_id=<YOUR_CLIENT_ID>&response_type=code&token_access_type=offline

Paste the token in a curl:

```
curl https://api.dropbox.com/oauth2/token \
     -d code=<token you just got> \
     -d grant_type=authorization_code \
     -u <your app key>:<your app secret>
```

Store to Google Cloud as a Secret called `DROPBOX_ACCESS_TOKEN`.

3. Run the queueing script

`poetry run python queue_files.py`
This will compare the list of Dropbox files on my computer against a list of already-processed files in MySQL. It will write PubSub messages with the file names that still need to be processed, which a Cloud Function will pick up (see next section). Through trial and error, I found pushing 100 file names to the queue every 5 seconds seems to get through the files mostly without any errors.

4. The Cloud Function

The Cloud Function is pretty simple: It reads the filename from the PubSub message, then it downloads that file from Dropbox and writes it to Google Cloud Storage. The Cloud Function is deployed via GitHub Actions in `.github/workflows/deploy.yml`.

5. Troubleshoot

Check the Cloud Function for errors. Most seem to be retriable, but `queue_files.py` occasionally needed to be adjusted to skip certain files (i.e. `.DS_Store`, `.dropbox`). Eventually, you should be able to run `queue_files.py` and it will report that there are 0 files to queue (i.e., you have loaded everything).
