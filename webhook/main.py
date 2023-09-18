from flask import Response
from google.cloud import pubsub_v1

TOPIC_NAME = "projects/greg-finley/topics/dropbox-queue-files"


def run(request):
    """Responds to any HTTP request.
    Args:
        request (flask.Request): HTTP request object.
    Returns:
        The response text or any set of values that can be turned into a
        Response object using
        `make_response <http://flask.pocoo.org/docs/1.0/api/#flask.Flask.make_response>`.
    """
    publisher = pubsub_v1.PublisherClient()
    publisher.publish(TOPIC_NAME, "Hello".encode("utf-8")).result()

    resp = Response(request.args.get("challenge"))
    resp.headers["Content-Type"] = "text/plain"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp
