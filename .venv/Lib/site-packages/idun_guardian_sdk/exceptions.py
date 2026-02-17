class IdunGuardianError(Exception):
    """Base class for exceptions in this SDK."""

    pass


class ConnectionError(IdunGuardianError):
    """Raised when a connection error occurs."""

    pass


class AuthenticationError(IdunGuardianError):
    """Raised when an authentication fails."""

    pass


class APIRequestError(IdunGuardianError):
    """Raised for errors during API requests."""

    pass
