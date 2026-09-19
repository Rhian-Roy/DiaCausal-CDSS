"""Passwords: Argon2id hashes (pwdlib), and the NIST SP 800-63B rules for choosing one."""

from pwdlib import PasswordHash

from app.settings import PASSWORD_MAX_CHARS, PASSWORD_MIN_CHARS

_hasher = PasswordHash.recommended()  # Argon2id, memory-hard

# Hash of a random password nobody knows: checked when the user ID does not exist, so a
# wrong user ID takes as long as a wrong password and the timing gives nothing away.
_DUMMY_HASH = _hasher.hash("no-such-user: timing equaliser 5f0c1d")

# The most common passwords in breach lists; NIST says refuse these.
COMMON = frozenset(
    """123456789012 password1234 passwordpassword qwertyuiop12 111111111111 123123123123
    iloveyou1234 adminadmin12 welcome12345 letmein12345 abc123456789 1q2w3e4r5t6y qwerty123456
    password@123 password#123 doctor123456 hospital1234 diabetes1234 metformin123 000000000000
    changeme1234 administrator p@ssw0rd1234 india1234567 sunshine1234 football1234""".split()
)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if password_hash is None:
        _hasher.verify(password, _DUMMY_HASH)
        return False
    return _hasher.verify(password, password_hash)


def password_problem(password: str, user_id: str) -> str | None:
    """Why this password may not be used, or None if it is fine."""
    if len(password) < PASSWORD_MIN_CHARS:
        return f"The password must be at least {PASSWORD_MIN_CHARS} characters (a short sentence works well)."
    if len(password) > PASSWORD_MAX_CHARS:
        return f"The password must be at most {PASSWORD_MAX_CHARS} characters."
    lowered = password.casefold()
    if lowered in COMMON or len(set(lowered)) < 4:
        return "That password is too common or too simple. Choose another."
    if user_id.casefold() in lowered:
        return "The password must not contain the user ID."
    return None
