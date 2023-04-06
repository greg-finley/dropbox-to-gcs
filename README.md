# dropbox-to-gcs

Move my whole Dropbox to GCS

# VM setup

```
sudo apt-get update
sudo apt-get install git python3-distutils -y
curl -sSL https://install.python-poetry.org | python3 -
sudo apt install python3 python3-dev python3-venv -y
echo 'export PATH="/home/gregoryfinley/.local/bin:$PATH"' >> .bashrc
source .bashrc
git clone https://github.com/greg-finley/dropbox-to-gcs
cd dropbox-to-gcs && poetry install
```
