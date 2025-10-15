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
from functools import reduce
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
        self._scheduled: dict[str, asyncio.Task] = {}
        self._total_executed: int = 0
        self._lock = asyncio.Lock()

    def total_evaluated_inputs(self) -> int:
        """
         Returns the total number of executed (cached) inputs
        :return:
        """
        return self._total_executed

    def total_cached_inputs(self) -> int:
        """
         Returns number of cached inputs
        :return:
        """
        return len(self._cache)

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
            case cassandra.Unauthorized | cassandra.RequestValidationException | cassandra.AuthenticationFailed:
                return TransientCachingError
            case (
                cassandra.Timeout
                | cassandra.Unavailable
                | cassandra.ReadTimeout
                | cassandra.WriteTimeout
                | cassandra.OperationTimedOut
                | cassandra.ReadFailure
                | cassandra.ReadFailure
                | cassandra.CoordinationFailure
            ):
                return TransientCachingError
            case _:
                return FatalCachingError

    async def resolve(
        self,
        *readers_or_processors: InputObject[TPayload, TResult],
        **kwargs,
    ) -> dict[str, TResult | None]:
        """
        Concurrently resolve `data` property of all readers by invoking their `read` method.
        """

        async def _execute(nexus_input: InputObject) -> TResult:
            async with self._lock:
                self._total_executed += 1

            async with nexus_input as instance:
                result: TResult | None = None
                try:
                    result = await nexus_input.process(**kwargs)
                finally:
                    async with self._lock:
                        self._cache[instance.cache_key()] = result

            return result

        async with self._lock:
            to_schedule = [rp for rp in readers_or_processors if rp.cache_key() not in self._scheduled]
            for to_schedule_object in to_schedule:
                self._scheduled[to_schedule_object.cache_key()] = asyncio.create_task(_execute(to_schedule_object))

        async def _wait_for_cache(
            *inputs: InputObject[TPayload, TResult],
        ) -> dict[str, TResult | None]:
            num_cached = 0
            while num_cached != len(inputs):
                num_cached = reduce(
                    lambda cached, input_object: cached + 1 if input_object.cache_key() in self._cache else cached,
                    readers_or_processors,
                    0,
                )
                for scheduled_object_key, scheduled_object in self._scheduled.items():
                    if scheduled_object.done() and scheduled_object.exception() is not None:
                        raise self._resolve_exc_type(scheduled_object.exception())(
                            scheduled_object_key
                        ) from scheduled_object.exception()

                await asyncio.sleep(0.1)

            return {
                reader_or_processor.__class__.alias(): reader_or_processor.data
                for reader_or_processor in inputs
                if reader_or_processor.cache_key() in self._cache
            }

        return await _wait_for_cache(*readers_or_processors)
