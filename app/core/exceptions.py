"""Errors shared by user use cases and persistence adapters."""


class UserAlreadyExistsError(Exception):
    """A user's id, username, or email conflicts with an existing user."""


class UserNotFoundError(Exception):
    """The requested user does not exist."""
