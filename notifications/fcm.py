from firebase_admin import messaging

from .firebase import *


def send_push_notification(
    token,
    title,
    body,
    data=None
):

    if not token:
        return False

    try:

        message = messaging.Message(

            notification=
            messaging.Notification(
                title=title,
                body=body
            ),

            token=token,

            data=data or {}
        )

        response = messaging.send(
            message
        )

        print(
            "FCM Success:",
            response
        )

        return True

    except Exception as e:

        print(
            "FCM Error:",
            str(e)
        )

        return False