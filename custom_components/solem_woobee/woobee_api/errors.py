"""Public errors; timeout is connectivity failure, not proof of auth rejection."""

class WooBeeError(Exception):
    """Base client failure."""

class AuthenticationError(WooBeeError, RuntimeError):
    """Authentication required or explicitly rejected."""

class ConnectivityError(WooBeeError):
    """BLE connection or transport failed; reconnect before reuse."""

class SessionTimeoutError(ConnectivityError, TimeoutError):
    """The operation exceeded its total deadline."""

class InvalidResponseError(WooBeeError, ValueError):
    """A response cannot be interpreted safely."""
