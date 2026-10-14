"""
InspireWorks demo IVR on Plivo.

Call flow (all driven by Plivo XML returned from this server):

  outbound call --> /answer          "Enter your 4-digit OTP"
                    /verify-otp      wrong -> "Incorrect" -> back to /answer
                                     right -> /language
                    /language        "Press 1 for English, 2 for Spanish"
                    /language-select invalid -> repeat /language
                    /menu?lang=xx    "Press 1 for audio, 2 for an associate"
                    /menu-select     1 -> <Play> mp3, then back to menu
                                     2 -> <Dial> associate number
                                     invalid -> repeat /menu
"""
import logging
import threading
import time
from xml.sax.saxutils import escape

import plivo
from flask import Flask, Response, jsonify, render_template, request

import config

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ivr")

# Prompts, keyed by language
TEXT = {
    "en": {
        "menu": "Press 1 to listen to a short audio message. Press 2 to speak with a live associate.",
        "invalid": "Sorry, that is not a valid option.",
        "no_input": "We did not receive any input.",
        "playing": "Here is your audio message.",
        "after_audio": "Returning to the main menu.",
        "connecting": "Please hold while we connect you to an associate.",
        "dial_failed": "Sorry, the associate is not available right now. Goodbye.",
    },
    "es": {
        "menu": "Presione 1 para escuchar un breve mensaje de audio. Presione 2 para hablar con un asociado.",
        "invalid": "Lo sentimos, esa no es una opción válida.",
        "no_input": "No recibimos ninguna respuesta.",
        "playing": "Aquí está su mensaje de audio.",
        "after_audio": "Volviendo al menú principal.",
        "connecting": "Por favor espere mientras lo conectamos con un asociado.",
        "dial_failed": "Lo sentimos, el asociado no está disponible. Adiós.",
    },
}


# ---------------------------------------------------------------- live call events
# In-memory timeline of the current call, shown live on the web page.
# One demo call at a time, so a single list is enough (no database).
EVENTS: list[dict] = []
_lock = threading.Lock()


def event(stage: str, text: str, kind: str = "info") -> None:
    """stage: dial | otp | lang | menu | end ; kind: info | ok | warn | err"""
    with _lock:
        EVENTS.append({"id": len(EVENTS), "t": time.time(), "stage": stage, "kind": kind, "text": text})


def reset_events() -> None:
    with _lock:
        EVENTS.clear()


# ---------------------------------------------------------------- helpers
def url(path: str) -> str:
    """Absolute URL Plivo should call back. Uses BASE_URL (ngrok) if set."""
    base = config.BASE_URL or request.url_root.rstrip("/")
    return f"{base}{path}"


def speak(text: str, lang: str = "en") -> str:
    l = config.LANGS[lang]
    return f'<Speak language="{l["code"]}" voice="{l["voice"]}">{escape(text)}</Speak>'


def xml(body: str) -> Response:
    out = f'<?xml version="1.0" encoding="UTF-8"?>\n<Response>{body}</Response>'
    log.info("XML -> %s", out.replace("\n", ""))
    return Response(out, mimetype="application/xml")


def get_digits(action: str, prompt_xml: str, num_digits: int) -> str:
    return (
        f'<GetDigits action="{escape(action)}" method="POST" numDigits="{num_digits}" '
        f'timeout="10" digitTimeout="5" retries="1">'
        f"{prompt_xml}</GetDigits>"
    )


def redirect(path: str) -> str:
    return f'<Redirect method="POST">{escape(url(path))}</Redirect>'


def lang_param() -> str:
    lang = request.args.get("lang", "en")
    return lang if lang in TEXT else "en"


def digits() -> str:
    return (request.values.get("Digits") or "").strip()


# ---------------------------------------------------------------- web UI / trigger
@app.get("/")
def index():
    return render_template("index.html", default_to=config.DEFAULT_TO_NUMBER,
                           from_number=config.PLIVO_NUMBER, base_url=config.BASE_URL)


def place_call(to_number: str) -> str:
    if not config.BASE_URL:
        raise RuntimeError("BASE_URL is not set (your public ngrok URL).")
    client = plivo.RestClient(config.PLIVO_AUTH_ID, config.PLIVO_AUTH_TOKEN)
    resp = client.calls.create(
        from_=config.PLIVO_NUMBER,
        to_="".join(ch for ch in to_number if ch.isdigit()),
        answer_url=f"{config.BASE_URL}/answer",
        answer_method="POST",
        hangup_url=f"{config.BASE_URL}/hangup",
        hangup_method="POST",
    )
    reset_events()
    event("dial", f"Calling +{''.join(ch for ch in to_number if ch.isdigit())} from +{config.PLIVO_NUMBER}")
    return resp.request_uuid


@app.get("/events")
def events():
    since = request.args.get("since", default=0, type=int)
    with _lock:
        return jsonify(events=EVENTS[since:])


@app.post("/call")
def call():
    data = request.get_json(silent=True) or request.form
    to_number = (data.get("to") or "").strip() or config.DEFAULT_TO_NUMBER
    if not to_number:
        return jsonify(ok=False, error="No destination number given"), 400
    try:
        uuid = place_call(to_number)
        log.info("Outbound call queued to %s, request_uuid=%s", to_number, uuid)
        return jsonify(ok=True, request_uuid=uuid, to=to_number)
    except Exception as e:  # surface Plivo errors to the UI
        log.exception("Call failed")
        return jsonify(ok=False, error=str(e)), 500


# ---------------------------------------------------------------- Level 0: OTP
@app.route("/answer", methods=["GET", "POST"])
def answer():
    retry = request.args.get("retry") == "1"
    if not retry:
        event("otp", "Call answered", "ok")
    event("otp", "Asking for 4-digit OTP")
    intro = "" if retry else speak("Welcome to the InspireWorks demo.")
    prompt = speak("Please enter your 4 digit O T P.")
    return xml(
        intro
        + get_digits(url("/verify-otp"), prompt, num_digits=4)
        + speak("We did not receive any input.")
        + redirect("/answer?retry=1")
    )


@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    entered = digits()
    log.info("OTP entered: %r (expected %r)", entered, config.OTP)
    if entered == config.OTP:
        event("otp", f"OTP {entered} correct — caller verified", "ok")
        return xml(speak("Thank you. You have been verified.") + redirect("/language"))
    event("otp", f"OTP {entered or '(none)'} incorrect — re-prompting", "err")
    return xml(speak("The O T P you entered is incorrect. Please try again.")
               + redirect("/answer?retry=1"))


# ---------------------------------------------------------------- Level 1: language
@app.route("/language", methods=["GET", "POST"])
def language():
    event("lang", "Level 1: language menu")
    prompt = (speak("For English, press 1.", "en")
              + speak("Para español, oprima 2.", "es"))
    return xml(
        get_digits(url("/language-select"), prompt, num_digits=1)
        + speak("We did not receive any input.")
        + redirect("/language")
    )


@app.route("/language-select", methods=["GET", "POST"])
def language_select():
    d = digits()
    log.info("Language choice: %r", d)
    if d == "1":
        event("lang", "Pressed 1 — English", "ok")
        return xml(redirect("/menu?lang=en"))
    if d == "2":
        event("lang", "Pressed 2 — Spanish", "ok")
        return xml(redirect("/menu?lang=es"))
    event("lang", f"Pressed {d or 'nothing'} — invalid, repeating", "warn")
    return xml(speak("Sorry, that is not a valid option.") + redirect("/language"))


# ---------------------------------------------------------------- Level 2: action
@app.route("/menu", methods=["GET", "POST"])
def menu():
    lang = lang_param()
    t = TEXT[lang]
    event("menu", f"Level 2: action menu ({'English' if lang == 'en' else 'Spanish'})")
    return xml(
        get_digits(url(f"/menu-select?lang={lang}"), speak(t["menu"], lang), num_digits=1)
        + speak(t["no_input"], lang)
        + redirect(f"/menu?lang={lang}")
    )


@app.route("/menu-select", methods=["GET", "POST"])
def menu_select():
    lang = lang_param()
    t = TEXT[lang]
    d = digits()
    log.info("Menu choice (%s): %r", lang, d)

    if d == "1":
        event("menu", "Pressed 1 — playing audio message", "ok")
        return xml(
            speak(t["playing"], lang)
            + f"<Play>{escape(config.AUDIO_URL)}</Play>"
            + speak(t["after_audio"], lang)
            + redirect(f"/menu?lang={lang}")
        )
    if d == "2":
        event("menu", f"Pressed 2 — forwarding to associate +{config.ASSOCIATE_NUMBER}", "ok")
        return xml(
            speak(t["connecting"], lang)
            + f'<Dial callerId="{config.PLIVO_NUMBER}" timeout="30" '
            f'callbackUrl="{escape(url("/dial-events"))}" callbackMethod="POST">'
            f"<Number>{config.ASSOCIATE_NUMBER}</Number></Dial>"
            + speak(t["dial_failed"], lang)
        )
    event("menu", f"Pressed {d or 'nothing'} — invalid, repeating", "warn")
    return xml(speak(t["invalid"], lang) + redirect(f"/menu?lang={lang}"))


# ---------------------------------------------------------------- logging
@app.route("/hangup", methods=["GET", "POST"])
def hangup():
    v = request.values
    log.info("Call ended: %s", dict(v))
    dur = v.get("Duration")
    event("end", f"Call ended — {v.get('HangupCause', 'hangup')}" + (f" ({dur}s)" if dur else ""), "info")
    return "OK"


@app.route("/dial-events", methods=["GET", "POST"])
def dial_events():
    v = request.values
    log.info("Dial event: %s", dict(v))
    action = v.get("DialAction", "")
    if action == "answer":
        event("menu", "Associate answered — caller connected", "ok")
    elif action == "hangup":
        event("menu", f"Associate leg ended — {v.get('DialBLegHangupCause', 'hangup')}", "info")
    return "OK"


if __name__ == "__main__":
    missing = [k for k in ("PLIVO_AUTH_ID", "PLIVO_AUTH_TOKEN", "BASE_URL") if not getattr(config, k)]
    if missing:
        log.warning("Missing config: %s  (see README / .env)", ", ".join(missing))
    app.run(host="0.0.0.0", port=config.PORT, debug=False)
