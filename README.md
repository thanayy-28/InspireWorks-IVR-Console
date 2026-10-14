# InspireWorks IVR Demo (Plivo Voice API)

A small Flask app that places an outbound call with Plivo and runs a multi-level IVR:

1. **Outbound call** from `+91 80354 54161` to your phone (triggered from a web page or CLI).
2. **OTP authentication** — caller enters a 4-digit OTP (birthdate in `DDMM`, hardcoded). Wrong OTP → re-prompt until correct.
3. **Level 1 – language**: `1` English, `2` Spanish.
4. **Level 2 – action** (in the chosen language): `1` play an MP3, `2` forward to a live associate (`02264236412`).

Invalid or missing input at any level replays the current prompt.

## Call flow

```
POST /call ──► Plivo dials your phone ──► /answer        "Enter your 4-digit OTP"
                                          /verify-otp    wrong → "Incorrect" → /answer
                                                         right → /language
                                          /language      "1 English, 2 Español"
                                          /language-select  invalid → /language
                                          /menu?lang=xx  "1 audio, 2 associate"
                                          /menu-select   1 → <Play> MP3 → back to /menu
                                                         2 → <Dial> associate
                                                         invalid → /menu
                                          /hangup        logs call summary
```

Each endpoint returns Plivo XML (`<GetDigits>`, `<Speak>`, `<Play>`, `<Dial>`, `<Redirect>`). State (chosen language) is carried in the callback URL, so no database or session is needed.

## Project layout

| File | Purpose |
|---|---|
| `app.py` | Flask server: call trigger + all Plivo XML endpoints |
| `config.py` | Numbers, **hardcoded OTP**, audio URL; reads secrets from `.env` |
| `make_call.py` | CLI to trigger the call |
| `templates/index.html` | Web console: "Call me" button + live timeline of the call (OTP attempts, menu choices, forwarding) |
| `.env.example` | Template for credentials |

## Prerequisites

- Python 3.9+
- [ngrok](https://ngrok.com/download) (free account) — Plivo needs a public URL to fetch the XML
- Plivo credentials: **Auth ID** and **Auth Token** (from the Plivo console)

## Setup

```bash
cd plivo-ivr
python -m venv .venv
# macOS/Linux:  source .venv/bin/activate
# Windows:      .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # Windows: copy .env.example .env
```

Edit `.env`:

```
PLIVO_AUTH_ID=<your Auth ID>
PLIVO_AUTH_TOKEN=<your Auth Token>
PLIVO_NUMBER=918035454161
ASSOCIATE_NUMBER=912264236412
TO_NUMBER=91XXXXXXXXXX        # optional, your phone
BASE_URL=                     # filled in step 2 below
```

Set your OTP in `config.py`:

```python
OTP = "1503"   # your birthdate as DDMM
```

## Run

1. **Start a tunnel** (terminal 1):
   ```bash
   ngrok http 5000
   ```
   Copy the `https://….ngrok-free.app` URL into `BASE_URL` in `.env`.

2. **Start the server** (terminal 2):
   ```bash
   python app.py
   ```

3. **Trigger the call**, either:
   - open http://localhost:5000, enter your number, click **Call me**, or
   - `python make_call.py +91XXXXXXXXXX`

## Test script (what the demo shows)

1. Answer the call → "Please enter your 4 digit OTP".
2. Enter a **wrong** OTP (e.g. `1111`) → "incorrect, try again".
3. Enter the **correct** OTP → "You have been verified".
4. Language menu → press `9` (invalid, re-prompt), then `1` or `2`.
5. Action menu → press `1` → audio plays, then menu repeats.
6. Press `2` → call is forwarded to the associate number.

The web console at http://localhost:5000 shows each step live as it happens (polls `GET /events`), and every XML response and digit pressed is also logged in the server terminal.

## Notes

- `.env` is git-ignored — credentials never go into the repo.
- Audio URL can be changed with `AUDIO_URL` in `.env` (any public MP3).
- If the account is a Plivo trial, the destination number must be verified in the console (Phone Numbers → Sandbox Numbers).
- If the free ngrok URL changes after a restart, update `BASE_URL` and restart `app.py`.
