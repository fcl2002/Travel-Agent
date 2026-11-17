"""Errors shared by user use cases and persistence adapters."""


class UserAlreadyExistsError(Exception):
    """A user's id, username, or email conflicts with an existing user."""


class UserNotFoundError(Exception):
    """The requested user does not exist."""


class AuthenticationError(Exception):
    """Credentials or the access token cannot authenticate an active user."""


class AuthRateLimitError(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
