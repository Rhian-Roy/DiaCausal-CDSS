"""CAPTCHA (bot check) behind a small interface, so a hosted service such as Cloudflare
Turnstile can replace it later without touching the sign-in code.

The built-in provider uses the offline Python `captcha` library: an image and a spoken
version of the same 6 digits (its voices say 0-9 only, so digits keep image and audio
the same). The answer stays on the server, works once, and expires after 5 minutes.

A CAPTCHA is NOT a second factor: it asks "is this a person?", not "is this the right
person?". It slows down bots guessing passwords; MFA protects the account.
"""

import base64
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from captcha.audio import AudioCaptcha
from captcha.image import ImageCaptcha
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth import clock
from app.db.models import CaptchaChallenge
from app.settings import CAPTCHA_DIGITS, CAPTCHA_PER_IP_PER_MINUTE, CAPTCHA_SECONDS


@dataclass(frozen=True)
class Challenge:
    id: str
    image_data_url: str


class TooManyChallenges(Exception):
    pass


class CaptchaProvider(Protocol):
    def new_challenge(self, db: Session, ip: str) -> Challenge: ...
    def audio(self, db: Session, challenge_id: str) -> bytes | None: ...
    def verify(self, db: Session, challenge_id: str, answer: str) -> bool: ...


class LocalCaptcha:
    """Offline image + audio CAPTCHA with the `captcha` library."""

    def __init__(self) -> None:
        self._image = ImageCaptcha(width=280, height=90)
        self._audio = AudioCaptcha()

    def new_challenge(self, db: Session, ip: str) -> Challenge:
        now = clock.now()
        db.execute(delete(CaptchaChallenge).where(CaptchaChallenge.created_at < now - timedelta(seconds=CAPTCHA_SECONDS)))
        recent = db.scalar(
            select(func.count()).where(
                CaptchaChallenge.ip == ip, CaptchaChallenge.created_at >= now - timedelta(minutes=1)
            )
        )
        if recent >= CAPTCHA_PER_IP_PER_MINUTE:
            db.commit()
            raise TooManyChallenges

        answer = "".join(secrets.choice("0123456789") for _ in range(CAPTCHA_DIGITS))
        challenge = CaptchaChallenge(id=secrets.token_urlsafe(24), answer=answer, created_at=now, ip=ip)
        db.add(challenge)
        db.commit()
        png = self._image.generate(answer).getvalue()
        return Challenge(challenge.id, "data:image/png;base64," + base64.b64encode(png).decode())

    def _live(self, db: Session, challenge_id: str) -> CaptchaChallenge | None:
        challenge = db.get(CaptchaChallenge, challenge_id)
        if challenge is None:
            return None
        if clock.now() - challenge.created_at > timedelta(seconds=CAPTCHA_SECONDS):
            db.delete(challenge)
            db.commit()
            return None
        return challenge

    def audio(self, db: Session, challenge_id: str) -> bytes | None:
        challenge = self._live(db, challenge_id)
        return None if challenge is None else bytes(self._audio.generate(challenge.answer))

    def verify(self, db: Session, challenge_id: str, answer: str) -> bool:
        challenge = self._live(db, challenge_id)
        if challenge is None:
            return False
        db.delete(challenge)  # single use, right or wrong
        db.commit()
        typed = "".join(answer.split())
        return secrets.compare_digest(typed.encode(), challenge.answer.encode())


provider: CaptchaProvider = LocalCaptcha()
