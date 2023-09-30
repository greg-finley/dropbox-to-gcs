import json
import os
from time import sleep

import mysql.connector
from google.cloud import pubsub_v1

TOPIC_NAME = "projects/greg-finley/topics/dropbox-backup"

mysql_config = json.loads(os.environ["MYSQL_CONFIG"])

mysql_connection = mysql.connector.connect(
    host=mysql_config["MYSQL_HOST"],
    user=mysql_config["MYSQL_USERNAME"],
    passwd=mysql_config["MYSQL_PASSWORD"],
    database=mysql_config["MYSQL_DATABASE"],
    ssl_ca=os.environ.get("SSL_CERT_FILE", "/etc/ssl/certs/ca-certificates.crt"),
)
mysql_connection.autocommit = True


def run(request):
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
