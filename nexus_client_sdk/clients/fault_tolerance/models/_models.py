from typing import TypeVar, final

from nexus_client_sdk.nexus.exceptions import FatalNexusError

TExecuteResult = TypeVar("TExecuteResult")


@final
class NexusReceiverResultNotCommittedError(BaseException):
    """
    Error to raise when result is not committed
    """


@final
class NexusSchedulingError(BaseException):
    """
    Error raised for SCHEDULING_FAILED requests. This class is used to enable retries for this lifecycle stage in certain cases.
    """


@final
class NexusClientRuntimeError(FatalNexusError):
    """
    Fatal error to be thrown from the scheduler client, to prevent Nexus apps from retrying.
    """

    def __init__(self, description: str) -> None:
        super().__init__()
        self._description = description

    def __str__(self) -> str:
        return self._description
