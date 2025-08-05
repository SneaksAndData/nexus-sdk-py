"""
 Simple in-memory cache for readers and processors
"""

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

import asyncio
from typing import final, Any

import deltalake.exceptions
import cassandra

from nexus_client_sdk.nexus.abstractions.input_object import InputObject
from nexus_client_sdk.nexus.abstractions.nexus_object import TResult, TPayload
from nexus_client_sdk.nexus.exceptions.cache_errors import (
    FatalCachingError,
    TransientCachingError,
)


@final
class InputCache:
    """
    In-memory cache for Nexus input readers/processors
    """

    def __init__(self):
        self._cache: dict[str, Any] = {}

    def _resolve_exc_type(self, ex: BaseException) -> type[FatalCachingError] | type[TransientCachingError]:
        """
        Resolve base exception into a specific Nexus exception.
        """

        match type(ex):
            case (
                deltalake.exceptions.TableNotFoundError
                | deltalake.exceptions.DeltaProtocolError
                | deltalake.exceptions.CommitFailedError
                | deltalake.exceptions.DeltaProtocolError
                | deltalake.exceptions.SchemaMismatchError
            ):
                return TransientCachingError
            case cassandra.Unauthorized, cassandra.RequestValidationException, cassandra.AuthenticationFailed:
                return TransientCachingError
            case cassandra.Timeout, cassandra.Unavailable, cassandra.ReadTimeout, cassandra.WriteTimeout, cassandra.OperationTimedOut, cassandra.ReadFailure, cassandra.ReadFailure, cassandra.CoordinationFailure:
                return TransientCachingError
            case _:
                return FatalCachingError

    async def resolve(
        self,
        *readers_or_processors: InputObject[TPayload, TResult],
        **kwargs,
    ) -> dict[str, TResult]:
        """
        Concurrently resolve `data` property of all readers by invoking their `read` method.
        """

        def get_result(alias: str, completed_task: asyncio.Task) -> TResult:
            object_exc = completed_task.exception()
            if object_exc:
                raise self._resolve_exc_type(object_exc)(alias) from object_exc

            return completed_task.result()

        async def _execute(nexus_input: InputObject) -> TResult:
            async with nexus_input as instance:
                result = await nexus_input.process(**kwargs)

            self._cache[instance.cache_key()] = result

            return result

        cached = {
            reader_or_processor.__class__.alias(): reader_or_processor.data
            for reader_or_processor in readers_or_processors
            if reader_or_processor.cache_key() in self._cache
        }
        if len(cached) == len(readers_or_processors):
            return cached

        read_tasks: dict[str, asyncio.Task] = {
            reader.__class__.alias(): asyncio.create_task(_execute(reader))
            for reader in readers_or_processors
            if reader.cache_key() not in self._cache
        }

        if len(read_tasks) > 0:
            await asyncio.wait(fs=read_tasks.values())

        return {alias: get_result(alias, task) for alias, task in read_tasks.items()} | cached
