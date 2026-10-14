"""
CLI trigger for the outbound call.

    python make_call.py +91XXXXXXXXXX
    python make_call.py            # uses TO_NUMBER from .env

The Flask server (app.py) and ngrok must already be running.
"""
import sys

import config
from app import place_call

to = sys.argv[1] if len(sys.argv) > 1 else config.DEFAULT_TO_NUMBER
if not to:
    sys.exit("Usage: python make_call.py <phone number>   (or set TO_NUMBER in .env)")

print(f"Calling {to} from +{config.PLIVO_NUMBER} ...")
print("Request UUID:", place_call(to))
