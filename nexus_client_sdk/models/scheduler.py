"""Scheduler CGO-Python models"""

#  Copyright (c) 2023-2026. ECCO Data & AI and other project contributors.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import ctypes
from dataclasses import dataclass
from typing import final, Self

from nexus_client_sdk.clients.cwrapper import CLIB
from nexus_client_sdk.models.common import PySdkType


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
            and self.request_id is None
            and self.result_uri is None
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


@final
class SdkRequestMetadata(ctypes.Structure):
    """
    Request metadata response model
    """

    _fields_ = [
        ("algorithm", ctypes.c_char_p),
        ("id", ctypes.c_char_p),
        ("algorithm_failure_cause", ctypes.c_char_p),
        ("algorithm_failure_details", ctypes.c_char_p),
        ("api_version", ctypes.c_char_p),
        ("applied_configuration", ctypes.c_char_p),
        ("configuration_overrides", ctypes.c_char_p),
        ("content_hash", ctypes.c_char_p),
        ("job_uid", ctypes.c_char_p),
        ("last_modified", ctypes.c_char_p),
        ("lifecycle_stage", ctypes.c_char_p),
        ("parent_job", ctypes.c_char_p),
        ("payload_uri", ctypes.c_char_p),
        ("payload_valid_for", ctypes.c_char_p),
        ("received_at", ctypes.c_char_p),
        ("received_by_host", ctypes.c_char_p),
        ("result_uri", ctypes.c_char_p),
        ("sent_at", ctypes.c_char_p),
        ("tag", ctypes.c_char_p),
        ("client_error_type", ctypes.c_char_p),
        ("client_error_message", ctypes.c_char_p),
    ]

    def __del__(self):
        CLIB.FreeRequestMetadata(self)


@dataclass
class RequestMetadata(PySdkType):
    """
    Python counterpart for SdkRequestMetadata
    """

    algorithm: str | None
    id: str | None
    algorithm_failure_cause: str | None
    algorithm_failure_details: str | None
    api_version: str | None
    applied_configuration: dict[str, str] | None
    configuration_overrides: dict[str, str] | None
    content_hash: str | None
    job_uid: str | None
    last_modified: str | None
    lifecycle_stage: str | None
    parent_job: dict[str, str] | None
    payload_uri: str | None
    payload_valid_for: str | None
    received_at: str | None
    received_by_host: str | None
    result_uri: str | None
    sent_at: str | None
    tag: str | None

    @classmethod
    def from_sdk_result(cls, result: SdkRequestMetadata) -> Self | None:
        """
         Create an instance of this class from a SdkRequestMetadata
        :param result: An instance of SdkRequestMetadata
        :return:
        """
        if not result:
            return None

        return cls(
            algorithm=result.algorithm.decode() if result.algorithm else None,
            id=result.id.decode() if result.id else None,
            algorithm_failure_cause=result.algorithm_failure_cause.decode() if result.algorithm_failure_cause else None,
            algorithm_failure_details=result.algorithm_failure_details.decode()
            if result.algorithm_failure_details
            else None,
            api_version=result.api_version,
            applied_configuration=result.applied_configuration.decode() if result.applied_configuration else None,
            configuration_overrides=result.configuration_overrides.decode() if result.configuration_overrides else None,
            content_hash=result.content_hash.decode() if result.content_hash else None,
            job_uid=result.job_uid.decode() if result.job_uid else None,
            last_modified=result.last_modified.decode() if result.last_modified else None,
            lifecycle_stage=result.lifecycle_stage,
            parent_job=result.parent_job.decode() if result.parent_job else None,
            payload_uri=result.payload_uri.decode() if result.payload_uri else None,
            payload_valid_for=result.payload_valid_for.decode() if result.payload_valid_for else None,
            received_at=result.received_at.decode() if result.received_at else None,
            received_by_host=result.received_by_host.decode() if result.received_by_host else None,
            result_uri=result.result_uri.decode() if result.result_uri else None,
            sent_at=result.sent_at.decode() if result.sent_at else None,
            tag=result.tag.decode() if result.tag else None,
            client_error_type=result.client_error_type.decode() if result.client_error_type else None,
            client_error_message=result.client_error_message.decode() if result.client_error_message else None,
        )


@final
class SdkStringResult(ctypes.Structure):
    """
    Optional string result
    """

    _fields_ = [
        ("result", ctypes.c_char_p),
        ("client_error_type", ctypes.c_char_p),
        ("client_error_message", ctypes.c_char_p),
    ]

    def __del__(self):
        CLIB.FreeStringResult(self)


@dataclass
class StringResult(PySdkType):
    """
    Python counterpart for SdkStringResult
    """

    result: str

    @classmethod
    def from_sdk_result(cls, result: SdkStringResult) -> Self | None:
        """
          Create an instance of this class from a SdkStringResult
        :param result: An instance of SdkStringResult
        :return:
        """

        if not result:
            return None

        return cls(
            result=result.result.decode() if result.result else "",
            client_error_type=result.client_error_type.decode() if result.client_error_type else None,
            client_error_message=result.client_error_message.decode() if result.client_error_message else None,
        )
