import pytest
from pydantic import ValidationError

from app.schemas.auth import LoginRequest
from app.schemas.user import UserCreate, UserUpdate


@pytest.mark.parametrize("schema", [UserCreate, UserUpdate])
def test_password_policy(schema):
    account = {"username": "traveler", "email": "traveler@example.com"}
    for password in ("Abcdef1!", "A1!" + "a" * 125, "  Abcdef1!  ", "Abcdef1_"):
        user = schema(**account, password=password)
        assert user.password.get_secret_value() == password
        assert password not in repr(user)

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
            schema(**account, password=password)


def test_login_accepts_legacy_passwords():
    # Existing accounts can still attempt login with their original passwords.
    assert LoginRequest(email="traveler@example.com", password="legacy-password")


def test_password_update_is_optional_but_cannot_be_null():
    assert UserUpdate(username="updated").password is None
    assert UserUpdate(password="Abcdef1!").model_fields_set == {"password"}
    with pytest.raises(ValidationError):
        UserUpdate(password=None)
