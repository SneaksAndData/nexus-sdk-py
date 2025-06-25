"""Scheduler CGO-Python models"""
import ctypes
from dataclasses import dataclass
from typing import final, Self

from nexus_client_sdk.cwrapper import CLIB
from nexus_client_sdk.models.client_errors.go_http_errors import (
    SdkError,
    UnauthorizedError,
    BadRequestError,
    NotFoundError,
)


@final
class SdkRunResult(ctypes.Structure):
    """
    Golang sister data structure for RunResult.
    """

    _fields_ = [
        ("algorithm", ctypes.c_char_p),
        ("request_id", ctypes.c_char_p),
        ("result_uri", ctypes.c_char_p),
        ("run_error_message", ctypes.c_char_p),
        ("client_error_type", ctypes.c_char_p),
        ("client_error_message", ctypes.c_char_p),
        ("status", ctypes.c_char_p),
    ]

    def __del__(self):
        CLIB.FreeRunResult(self)


@dataclass
class PySdkType:
    """
    Base class for Python model type wrappers
    """

    client_error_type: str | None
    client_error_message: str | None

    def error(self) -> RuntimeError | None:
        """
         Parse Go client error into a corresponding Python error.
        :return:
        """
        match self.client_error_type:
            case "*models.SdkErr":
                return SdkError(self.client_error_message)
            case "*models.UnauthorizedError":
                return UnauthorizedError(self.client_error_message)
            case "*models.BadRequestError":
                return BadRequestError(self.client_error_message)
            case "*models.NotFoundError":
                return NotFoundError(self.client_error_message)
        return None


@dataclass
class RunResult(PySdkType):
    """
    Python SDK data structure for RunResult.
    """

    algorithm: str | None
    request_id: str | None
    result_uri: str | None
    run_error_message: str | None
    status: str | None

    @classmethod
    def from_sdk_result(cls, result: SdkRunResult) -> Self | None:
        """
         Create a RunResult from an SDKRunResult.
        :param result: SdkRunResult object returned from a CGO compiled function.
        :return:
        """
        if not result:
            return None

        obj = cls(
            algorithm=result.algorithm.decode() if result.algorithm else None,
            request_id=result.request_id.decode() if result.request_id else None,
            result_uri=result.result_uri.decode() if result.result_uri else None,
            run_error_message=result.run_error_message.decode() if result.run_error_message else None,
            client_error_type=result.client_error_type.decode() if result.client_error_type else None,
            client_error_message=result.client_error_message.decode() if result.client_error_message else None,
            status=result.status.decode() if result.status else None,
        )

        if obj.is_empty():
            return None

        return obj

    def is_empty(self) -> bool:
        """
         Checks if this object is empty (end of the response)
        :return:
        """
        return (
            self.algorithm is None
            or self.request_id is None
            or self.result_uri is None
            and self.run_error_message is None
            and self.status is None
            and self.client_error_type is None
            and self.client_error_message is None
        )


@final
class SdkAlgorithmRun(ctypes.Structure):
    """
    Golang sister data structure for AlgorithmRun.
    """

    _fields_ = [
        ("request_id", ctypes.c_char_p),
        ("client_error_type", ctypes.c_char_p),
        ("client_error_message", ctypes.c_char_p),
    ]

    def __del__(self):
        CLIB.FreeAlgorithmRun(self)


@dataclass
class AlgorithmRun(PySdkType):
    """
    Python SDK data structure for SdkAlgorithmRun.
    """

    request_id: str | None

    @classmethod
    def from_sdk_run(cls, algorithm_run: SdkAlgorithmRun) -> Self | None:
        """
         Create a RunResult from an SDKRunResult.
        :param algorithm_run: SdkAlgorithmRun object returned from a CGO compiled function.
        :return:
        """
        if not algorithm_run:
            return None

        return cls(
            request_id=algorithm_run.request_id.decode() if algorithm_run.request_id else None,
            client_error_type=algorithm_run.client_error_type.decode() if algorithm_run.client_error_type else None,
            client_error_message=algorithm_run.client_error_message.decode()
            if algorithm_run.client_error_message
            else None,
        )


@final
class SdkCustomRunConfiguration(ctypes.Structure):
    """
    Allowed configuration overrides for the run creation endpoint.
    """

    _fields_ = [
        ("version", ctypes.c_char_p),
        ("workgroup_name", ctypes.c_char_p),
        ("workgroup_group", ctypes.c_char_p),
        ("workgroup_kind", ctypes.c_char_p),
        ("cpu_limit", ctypes.c_char_p),
        ("memory_limit", ctypes.c_char_p),
    ]

    @classmethod
    def create(
        cls,
        *,
        version: str | None = None,
        workgroup_name: str | None = None,
        cpu_limit: str | None = None,
        memory_limit: str | None = None,
        workgroup_group: str = "science.sneaksanddata.com/v1",
        workgroup_kind: str = "NexusAlgorithmWorkgroup",
    ) -> Self:
        """
         Create an instance of this class.
        :param version: Algorithm version override
        :param workgroup_name: Algorithm workgroup name override
        :param workgroup_group: Algorithm workgroup group override
        :param workgroup_kind: Algorithm workgroup kind override
        :param cpu_limit: Run CPU limit override
        :param memory_limit: Run max memory limit override
        :return:
        """
        return cls(
            version=bytes(version, encoding="utf-8") if version else None,
            workgroup_name=bytes(workgroup_name, encoding="utf-8") if workgroup_name else None,
            workgroup_group=bytes(workgroup_group, encoding="utf-8") if workgroup_group else None,
            workgroup_kind=bytes(workgroup_kind, encoding="utf-8") if workgroup_kind else None,
            cpu_limit=bytes(cpu_limit, encoding="utf-8") if cpu_limit else None,
            memory_limit=bytes(memory_limit, encoding="utf-8") if memory_limit else None,
        )

    def as_pointer(self) -> ctypes.pointer:
        """
         Return a pointer to this SdkCustomRunConfiguration.
        :return:
        """
        return ctypes.pointer(self)


@final
class SdkParentRequest(ctypes.Structure):
    """
    Parent request model
    """

    _fields_ = [
        ("algorithm_name", ctypes.c_char_p),
        ("request_id", ctypes.c_char_p),
    ]

    @classmethod
    def create(cls, *, algorithm_name: str, request_id: str) -> Self:
        """
        Create an instance of this class.
        :param algorithm_name: Algorithm name of the parent request
        :param request_id: Request identifier of the parent request
        :return:
        """
        return cls(
            algorithm_name=bytes(algorithm_name, encoding="utf-8"), request_id=bytes(request_id, encoding="utf-8")
        )

    def as_pointer(self) -> ctypes.pointer:
        """
        Return a pointer to this SdkParentRequest.
        :return:
        """
        return ctypes.pointer(self)
