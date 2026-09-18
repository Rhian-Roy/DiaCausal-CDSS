"""Fixed settings for the API. Nothing in here is secret."""

# The request/response contract version. A client must send exactly this value.
SCHEMA_VERSION = "1.0"

# Longest text a single message part may carry, counted in characters.
MAX_TEXT_CHARS = 8000

# Most parts one message may carry. Stops a single request from being huge.
MAX_PARTS = 20

# Part types the API understands today. Add new ones here *and* in schemas.py.
SUPPORTED_PART_TYPES = ("text",)

# client_trace_id: 1-64 letters, digits, "-" or "_". Safe to print in logs.
TRACE_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"

INTENDED_USE = (
    "Research prototype for clinician evaluation; not a marketed medical device; "
    "not for unsupervised clinical use."
)
