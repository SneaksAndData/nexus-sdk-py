from typing import final


@final
class BadRequestError(RuntimeError):
    """
    Nexus client error returned if response decoding failed - in case of non-successful HTTP codes.
    """

    def __init__(self, *args, **kwargs):
        pass


@final
class NotFoundError(RuntimeError):
    """
    Nexus client error returned if response decoding failed - in case of non-successful HTTP codes.
    """

    def __init__(self, *args, **kwargs):
        pass


@final
class SdkError(RuntimeError):
    """
    Nexus client error returned if response decoding failed - in case of non-successful HTTP codes.
    """

    def __init__(self, *args, **kwargs):
        pass


@final
class UnauthorizedError(RuntimeError):
    """
    Nexus client error returned if response decoding failed - in case of non-successful HTTP codes.
    """

    def __init__(self, *args, **kwargs):
        pass
