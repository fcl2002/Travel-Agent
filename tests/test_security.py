from app.core.security import hash_password, verify_password


def test_argon2_hashing_and_verification():
    password = "  Uma senha com café!  "
    password_hash = hash_password(password)
    assert password_hash.startswith("$argon2id$")
    assert password_hash != password and hash_password(password) != password_hash
    assert verify_password(password, password_hash) is True
    assert verify_password(password.strip(), password_hash) is False
    assert verify_password("wrong-password", password_hash) is False
    assert verify_password(password, "invalid-hash") is False
