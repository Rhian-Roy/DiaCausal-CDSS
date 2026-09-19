"""6-digit authenticator codes (TOTP, RFC 6238) with pyotp.

- The shared secret is encrypted with Fernet (key DIACAUSAL_SECRET_KEY from backend/.env)
  before it goes into the database.
- A code is accepted one 30-second step early or late (clocks drift), and each step
  only once: `last_totp_step` remembers the newest step used.
"""

import base64
import io

import pyotp
import qrcode
import qrcode.image.svg
from cryptography.fernet import Fernet

from app.auth import clock
from app.secrets_env import secret_key

ISSUER = "DiaCausal"
STEP_SECONDS = 30


def _fernet() -> Fernet:
    return Fernet(secret_key())


def new_secret() -> str:
    return pyotp.random_base32(32)  # 160 bits, as RFC 4226 recommends


def encrypt(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


def key_groups(secret: str) -> list[str]:
    """ABCD EFGH ... — easier to type by hand (design 06)."""
    return [secret[i : i + 4] for i in range(0, len(secret), 4)]


def provisioning_uri(secret: str, user_id: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=user_id, issuer_name=ISSUER)


def qr_svg_data_url(uri: str) -> str:
    image = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    buffer = io.BytesIO()
    image.save(buffer)
    return "data:image/svg+xml;base64," + base64.b64encode(buffer.getvalue()).decode()


def matching_step(secret: str, code: str, after_step: int) -> int | None:
    """The time step `code` belongs to (now, one before or one after), if it is newer
    than `after_step`; otherwise None."""
    if not (len(code) == 6 and code.isascii() and code.isdigit()):
        return None
    totp = pyotp.TOTP(secret)
    current = totp.timecode(clock.now())
    for step in (current - 1, current, current + 1):
        if step > after_step and pyotp.utils.strings_equal(totp.generate_otp(step), code):
            return step
    return None
