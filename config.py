"""
App configuration.

Secrets (Auth ID / Auth Token) are read from environment variables / a .env file
so they never get committed. Everything else is plain config.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# --- Plivo credentials (set these in .env) ---------------------------------
PLIVO_AUTH_ID = os.getenv("PLIVO_AUTH_ID", "")
PLIVO_AUTH_TOKEN = os.getenv("PLIVO_AUTH_TOKEN", "")

# --- Phone numbers (E.164, no '+' needed for Plivo) -------------------------
# Plivo number the outbound call is made FROM.
PLIVO_NUMBER = os.getenv("PLIVO_NUMBER", "918035454161")

# Default number to call (your phone). Can also be entered in the web UI / CLI.
DEFAULT_TO_NUMBER = os.getenv("TO_NUMBER", "")

# Live associate number. Given as 02264236412 -> E.164 for India: 91 2264236412
ASSOCIATE_NUMBER = os.getenv("ASSOCIATE_NUMBER", "912264236412")

# --- OTP --------------------------------------------------------------------
# Hardcoded OTP = birthdate in DDMM format.  e.g. 15 March -> "2801"
# >>> CHANGE THIS TO YOUR OWN BIRTHDATE <<<
OTP = "2801"

# --- Public URL of this server (your ngrok URL) -----------------------------
# Plivo must be able to reach the XML endpoints, so this must be public.
# e.g. https://abcd-1234.ngrok-free.app   (no trailing slash)
BASE_URL = os.getenv("BASE_URL", "").rstrip("/")

# --- Audio played on Level 2, option 1 --------------------------------------
AUDIO_URL = os.getenv(
    "AUDIO_URL", "https://s3.amazonaws.com/plivocloud/music.mp3"
)

# --- Prompt languages -------------------------------------------------------
LANGS = {
    "en": {"code": "en-US", "voice": "WOMAN"},
    "es": {"code": "es-ES", "voice": "WOMAN"},
}

PORT = int(os.getenv("PORT", "5000"))
