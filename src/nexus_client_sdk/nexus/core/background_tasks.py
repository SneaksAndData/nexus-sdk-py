"""
Background task manager for asynchronous tasks.
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
from collections.abc import Coroutine
from typing import Any, final

from adapta.metrics import MetricsProvider
from injector import inject

from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory


@final
class BackgroundTaskManager:
    """
    Manages background tasks scheduled during an algorithm run.
    Holds strong references to tasks to prevent premature garbage collection,
    and awaits them during application shutdown.
    Failures in background tasks are logged and recorded via metrics, but never
    propagated as failures to the main execution flow.
    """

    @inject
    def __init__(self, logger_factory: LoggerFactory, metrics_provider: MetricsProvider):
        self._tasks: set[asyncio.Task] = set()
        self._logger = logger_factory.create_logger(self.__class__)
        self._metrics_provider = metrics_provider

    def activate(self) -> None:
        """
        Activates the background task manager and starts its logger.
        """
        self._logger.start()

    def shutdown(self) -> None:
        """
        Shuts down the background task manager and stops its logger.
        """
        self._logger.stop()

    def add_task(self, coro: Coroutine[Any, Any, Any], name: str | None = None) -> asyncio.Task:
        """
        Schedules a coroutine as an asyncio.Task, keeping a strong reference
        until completion to prevent premature GC, and tracking it for draining.

        :param coro: Coroutine to execute in background.
        :param name: Optional task name.
        :return: Created asyncio.Task.
        """
        self._logger.info("Adding background task {task_name}", task_name=name or "unnamed")
        task = asyncio.create_task(coro, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def drain(self, timeout: float | None = None) -> None:
        """
        Awaits all tracked background tasks to completion.
        Failures are logged and recorded as metrics, but never re-raised.

        :param timeout: Optional timeout in seconds to wait for tasks.
        """
        if not self._tasks:
            return

        tasks_to_drain = list(self._tasks)
        self._logger.info(
            "Awaiting {count} background task(s) before exit",
            count=len(tasks_to_drain),
        )

        try:
            done, pending = await asyncio.wait(tasks_to_drain, timeout=timeout)
        except Exception as ex:
            self._logger.error("Unexpected error while awaiting background tasks", exception=ex)
            return

        if pending:
            self._logger.warning(
                "{count} background task(s) did not complete within the timeout and remain pending",
                count=len(pending),
            )
            self._metrics_provider.gauge(
                metric_name="background_tasks_timeout",
                metric_value=len(pending),
            )

        failed_count = 0
        cancelled_count = 0
        succeeded_count = 0

        for task in done:
            if task.cancelled():
                self._logger.warning("Background task {task_name} was cancelled", task_name=task.get_name())
                cancelled_count += 1
            elif task.exception() is not None:
                self._logger.error(
                    "Background task {task_name} failed",
                    task_name=task.get_name(),
                    exception=task.exception(),
                )
                failed_count += 1
            else:
                succeeded_count += 1

        self._metrics_provider.gauge(
            metric_name="background_tasks_failed",
            metric_value=failed_count,
        )
        self._metrics_provider.gauge(
            metric_name="background_tasks_cancelled",
            metric_value=cancelled_count,
        )
        self._metrics_provider.gauge(
            metric_name="background_tasks_succeeded",
            metric_value=succeeded_count,
        )
