import pytest
from pydantic import ValidationError

from app.schemas.auth import LoginRequest
from app.schemas.user import UserCreate


def test_registration_password_policy():
    account = {"username": "traveler", "email": "traveler@example.com"}
    for password in ("Abcdef1!", "A1!" + "a" * 125, "  Abcdef1!  ", "Abcdef1_"):
        user = UserCreate(**account, password=password)
        assert user.password.get_secret_value() == password

    for password in (
        "Abcde1!",                # Too short.
        "A1!" + "a" * 126,        # Too long.
        "abcdef1!",               # Missing uppercase letter.
        "Abcdefg!",               # Missing digit.
        "Abcdef12",               # Missing special character.
        "Abcdef1 ",               # Whitespace is not a special character.
        "Abcdef1\n",              # Control characters are not special characters.
        "        ",
    ):
        with pytest.raises(ValidationError):
            UserCreate(**account, password=password)

    # Existing accounts can still attempt login with their original passwords.
    assert LoginRequest(email=account["email"], password="legacy-password")
