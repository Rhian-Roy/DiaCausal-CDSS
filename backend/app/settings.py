"""Fixed settings for the API. Nothing in here is secret."""

# The request/response contract version. A client must send exactly this value.
SCHEMA_VERSION = "1.0"

# Longest text a single message part may carry, counted in characters.
MAX_TEXT_CHARS = 8000

# Most parts one message may carry. Stops a single request from being huge.
MAX_PARTS = 20

# The largest request body the server will read at all, before anything else looks at it.
# Bigger than a 2 MB voice clip with room to spare; a chat message is a few kilobytes.
MAX_REQUEST_BYTES = 4 * 1024 * 1024

# Part types the API understands today. Add new ones here *and* in schemas.py.
# "patient" carries the structured patient details from the panel (app/patient_ranges.py).
SUPPORTED_PART_TYPES = ("text", "patient")

# client_trace_id: 1-64 letters, digits, "-" or "_". Safe to print in logs.
TRACE_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"

INTENDED_USE = (
    "Research prototype for clinician evaluation; not a marketed medical device; "
    "not for unsupervised clinical use."
)

# Version of the intended-use text a clinician acknowledges after signing in (design 07).
# Bump it when the text changes, so everyone reads and acknowledges it again.
INTENDED_USE_VERSION = "1"

# ── Sign-in (app/auth/) ─────────────────────────────────────────────────────
# Idle timeout: a shared ward computer left signed in is the main risk; 15 minutes
# is the usual clinical-workstation idle limit (NIST SP 800-63B allows up to 30 at AAL2).
SESSION_IDLE_SECONDS = 15 * 60
# Absolute timeout: one clinical shift; after it, sign in again even if active
# (NIST SP 800-63B AAL2: re-authenticate at least every 12 hours).
SESSION_ABSOLUTE_SECONDS = 8 * 60 * 60
# The page warns this long before the idle timeout (design 08).
SESSION_WARNING_SECONDS = 2 * 60
# Between password and 6-digit code: long enough to open an authenticator app.
LOGIN_PENDING_SECONDS = 5 * 60

# A CAPTCHA can be answered once, within 5 minutes.
CAPTCHA_SECONDS = 5 * 60
CAPTCHA_DIGITS = 6  # digits only: the audio CAPTCHA's built-in voices say 0-9 only

# Wrong passwords or codes before an account locks, and for how long. The lock clears
# on its own (design 03), and only attempts with a correct CAPTCHA count, so a bot
# cannot lock everyone out; an administrator can unlock sooner.
LOCKOUT_AFTER_FAILURES = 5
LOCKOUT_SECONDS = 15 * 60
# Growing delay per account: after the 3rd failure wait 2 s, then 4 s, 8 s ... (max 30 s).
DELAY_FROM_FAILURE = 3
DELAY_MAX_SECONDS = 30
# Per IP address (catches one machine trying many accounts): failures counted over 15
# minutes; from the 10th a growing delay, at 50 the address is blocked for 15 minutes.
IP_WINDOW_SECONDS = 15 * 60
IP_DELAY_FROM_FAILURE = 10
IP_BLOCK_AFTER_FAILURES = 50
# New CAPTCHAs per IP address per minute (stops filling the database with challenges).
CAPTCHA_PER_IP_PER_MINUTE = 30

# Passwords: NIST SP 800-63B — length matters, composition rules do not.
PASSWORD_MIN_CHARS = 12
PASSWORD_MAX_CHARS = 128

# ── Voice (app/voice/) ──────────────────────────────────────────────────────
VOICE_MAX_SECONDS = 30
VOICE_MAX_BYTES = 2 * 1024 * 1024  # 30 s of browser audio (Opus/AAC) is well under 1 MB
VOICE_PER_USER_PER_MINUTE = 10
