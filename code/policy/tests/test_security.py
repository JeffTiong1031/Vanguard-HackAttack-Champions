import hashlib
import uuid

from app.deps import get_conn
from app.security import (
    _SCRYPT_N, _SCRYPT_P, _SCRYPT_R,
    hash_password, hash_token, issue_session, new_token, session_org, verify_password,
)


def test_new_token_is_prefixed_and_its_hash_matches():
    plain, hashed = new_token("ENG")
    assert plain.startswith("ENG-")
    assert hash_token(plain) == hashed


def test_two_tokens_are_never_equal():
    assert new_token("ENG")[0] != new_token("ENG")[0]


def test_password_round_trips_and_rejects_the_wrong_one():
    stored = hash_password("hunter2")
    assert verify_password("hunter2", stored) is True
    assert verify_password("hunter3", stored) is False


def test_password_hash_is_salted_so_two_hashes_of_one_password_differ():
    assert hash_password("hunter2") != hash_password("hunter2")


def test_session_round_trip():
    conn = get_conn()
    oid = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO orgs (id, name, admin_password_hash) VALUES (%s, %s, 'x')",
        (oid, "Acme-" + oid),
    )
    conn.commit()
    token = issue_session(conn, oid)
    assert session_org(conn, token) == oid
    assert session_org(conn, "not-a-session") is None


# Finding 1: Algorithm pinning tests — guards against swapping hash_token and hash_password
def test_hash_token_is_exactly_sha256_length():
    """hash_token output must be exactly 64 lowercase hex chars (SHA-256 digest length)."""
    result = hash_token("ENG-test")
    assert len(result) == 64
    assert result == result.lower()
    assert all(c in "0123456789abcdef" for c in result)


def test_hash_token_matches_known_sha256_vector():
    """hash_token must match SHA-256, not scrypt or any other algorithm."""
    # Pre-computed SHA-256 of "ENG-test"
    expected = hashlib.sha256(b"ENG-test").hexdigest()
    result = hash_token("ENG-test")
    assert result == expected
    assert result == "a12e198078f588f704eeba0676cf04cf5d4e7d968413923577c7967ef0d70c10"


def test_hash_password_output_begins_with_scrypt_marker():
    """hash_password output must start with 'scrypt$' scheme marker."""
    result = hash_password("hunter2")
    assert result.startswith("scrypt$")


def test_hash_password_is_not_plain_sha256():
    """hash_password must use scrypt, not SHA-256. This catches accidental algorithm swap."""
    pw = "hunter2"
    stored = hash_password(pw)
    # If someone accidentally used SHA-256 instead of scrypt, this would match
    plain_sha256 = hashlib.sha256(pw.encode()).hexdigest()
    # The stored hash should NOT be just the SHA-256 digest
    assert not stored.endswith(plain_sha256)


def test_hash_password_uses_scrypt_with_correct_parameters():
    """Positive test: the stored digest must be the actual scrypt output of the password and salt.

    Catches bugs like f"scrypt${salt.hex()}${hashlib.sha256(pw + salt).hexdigest()}" which would
    be salted, carry the scrypt$ marker, and differ from unsalted SHA-256, but would not be
    the actual scrypt output.
    """
    pw = "hunter2"
    stored = hash_password(pw)

    # Parse the stored format: scrypt$<salt_hex>$<digest_hex>
    scheme, salt_hex, stored_digest_hex = stored.split("$")
    assert scheme == "scrypt"

    # Recompute scrypt with the stored salt and declared parameters
    salt = bytes.fromhex(salt_hex)
    recomputed = hashlib.scrypt(
        pw.encode(),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
    )
    recomputed_digest_hex = recomputed.hex()

    # The recomputed digest must match the stored one
    assert recomputed_digest_hex == stored_digest_hex


# Finding 2: Exception handling in verify_password
def test_verify_password_returns_false_on_corrupted_stored_value():
    """Malformed stored values (e.g., non-hex salt) must return False, not raise."""
    # Corrupted: non-hex characters in salt
    assert verify_password("hunter2", "scrypt$nothex$nothex") is False
    # Corrupted: only two components
    assert verify_password("hunter2", "scrypt$nothex") is False
    # Corrupted: empty salt
    assert verify_password("hunter2", "scrypt$$") is False
    # Corrupted: invalid hex characters
    assert verify_password("hunter2", "scrypt$zzzzzzzzzzzzzzzz$deadbeef") is False


def test_verify_password_returns_false_on_non_string_stored_value():
    """Non-string stored values (e.g., None) must return False, not raise AttributeError."""
    assert verify_password("hunter2", None) is False
