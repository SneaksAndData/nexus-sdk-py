"""
 Dependency injections.
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

import os
import re
from pydoc import locate
from typing import final, Any, Callable, Self

from adapta.storage.blob.base import StorageClient
from injector import Module, singleton, provider

from nexus_client_sdk.nexus.abstractions.algorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.logger_factory import (
    BootstrapLoggerFactory,
)
from nexus_client_sdk.nexus.abstractions.qes_factory import QueryEnabledStoreCollection
from nexus_client_sdk.nexus.abstractions.socket_provider import (
    ExternalSocketProvider,
)
from nexus_client_sdk.nexus.configurations.runtime_configuration import NEXUS_FRAMEWORK_CONFIGURATION
from nexus_client_sdk.nexus.core.serializers import (
    TelemetrySerializer,
    ResultSerializer,
)
from nexus_client_sdk.nexus.exceptions.error_map import NexusErrorMapCollection, NexusErrorMap
from nexus_client_sdk.nexus.exceptions.startup_error import (
    FatalStartupConfigurationError,
)


@final
class BootstrapLoggerFactoryModule(Module):
    """
    Logger factory module.
    """

    @singleton
    @provider
    def provide(self) -> BootstrapLoggerFactory:
        """
        DI factory method.
        """
        return BootstrapLoggerFactory()


@final
class QueryEnabledStoreCollectionModule(Module):
    """
    QES module.
    """

    @singleton
    @provider
    def provide(self) -> QueryEnabledStoreCollection:
        """
        DI factory method.
        """
        if NEXUS_FRAMEWORK_CONFIGURATION.default.services.query_enabled_store.enabled != "1":
            return QueryEnabledStoreCollection()

        try:
            return QueryEnabledStoreCollection().load_stores(
                NEXUS_FRAMEWORK_CONFIGURATION.default.services.query_enabled_store.store_connections
            )
        except Exception as e:
            raise FatalStartupConfigurationError(
                "Unable to initialize QES collection. Please ensure query_enabled_store.store_connections list property is defined in TOML configuration."
            ) from e


@final
class StorageClientModule(Module):
    """
    Storage client module.
    """

    @singleton
    @provider
    def provide(self) -> StorageClient:
        """
        DI factory method.
        """
        storage_client_class: type[StorageClient] = locate(
            NEXUS_FRAMEWORK_CONFIGURATION.default.result.storage_client_class
        )

        try:
            return storage_client_class.for_storage_path(path=NEXUS_FRAMEWORK_CONFIGURATION.default.result.output_path)
        except Exception as e:
            raise FatalStartupConfigurationError(
                "StorageClient cannot be created, configuration missing or invalid. Review the underlying exception."
            ) from e


@final
class ExternalSocketsModule(Module):
    """
    Storage client module.
    """

    @singleton
    @provider
    def provide(self) -> ExternalSocketProvider:
        """
        Dependency provider.
        """
        if (
            NEXUS_FRAMEWORK_CONFIGURATION.default.inputs.sockets
            and len(NEXUS_FRAMEWORK_CONFIGURATION.default.inputs.sockets) > 0
        ):
            return ExternalSocketProvider.from_dynaconf(NEXUS_FRAMEWORK_CONFIGURATION.default.inputs.sockets)

        return ExternalSocketProvider.empty()


@final
class ResultSerializerModule(Module):
    """
    Serialization format module for results.
    """

    @singleton
    @provider
    def provide(self) -> ResultSerializer:
        """
        DI factory method.
        """
        serializer = ResultSerializer()
        for serializer_class in NEXUS_FRAMEWORK_CONFIGURATION.default.result.serializers:
            serializer = serializer.with_format(locate(serializer_class))

        return serializer


@final
class TelemetrySerializerModule(Module):
    """
    Serialization format module for telemetry.
    """

    @singleton
    @provider
    def provide(self) -> TelemetrySerializer:
        """
        DI factory method.
        """
        serializer = TelemetrySerializer()
        for serializer_class in NEXUS_FRAMEWORK_CONFIGURATION.default.telemetry.serializers:
            serializer = serializer.with_format(locate(serializer_class))

        return serializer


@final
class CacheModule(Module):
    """
    Storage client module.
    """

    @singleton
    @provider
    def provide(self) -> InputCache:
        """
        Dependency provider.
        """
        loaded_error_map: dict[str, list[NexusErrorMap]] = {}
        for error_map_config in NEXUS_FRAMEWORK_CONFIGURATION.default.runtime.exceptions.scoped:
            if error_map_config["class_name"] not in loaded_error_map:
                loaded_error_map[error_map_config["class_name"]] = [NexusErrorMap.from_config(error_map_config)]
            else:
                loaded_error_map[error_map_config["class_name"]].append(NexusErrorMap.from_config(error_map_config))

        default_error: type[BaseException] = locate(
            NEXUS_FRAMEWORK_CONFIGURATION.default.runtime.exceptions.defaults.global_default
        )
        if default_error is None:
            raise FatalStartupConfigurationError(
                f"Unable to locate default error map class: {NEXUS_FRAMEWORK_CONFIGURATION.default.runtime.exceptions.defaults.global_default}"
            )

        map_instance = NexusErrorMapCollection(
            global_default=default_error,
            error_map=loaded_error_map,
        )
        return InputCache(map_instance)


@final
class Compressor:
    """
    Compression and decompression support for remote algorithm payloads.
    """

    def __init__(self, compress_import_path: str, decompress_import_path: str):
        self._compress_import_path = compress_import_path
        self._decompress_import_path = decompress_import_path
        self._compress_function: Callable[
            [
                bytes,
            ],
            bytes,
        ] = locate(self._compress_import_path)
        self._decompress_function: Callable[
            [
                bytes,
            ],
            bytes,
        ] = locate(self._decompress_import_path)

        if not self._compress_function:
            raise FatalStartupConfigurationError(
                f"Compression function '{self._compress_import_path}' could not be located."
            )
        if not self._decompress_function:
            raise FatalStartupConfigurationError(
                f"Decompression function '{self._decompress_import_path}' could not be located."
            )

    @classmethod
    def create(cls, compress_import_path: str, decompress_import_path: str) -> Self:
        """
        Factory method to create a compressor instance.
        """
        try:
            return cls(compress_import_path, decompress_import_path)
        except Exception as ex:
            raise FatalStartupConfigurationError("compress or decompress import path could not be resolved.") from ex

    def compress(self, data: bytes) -> bytes:
        """
        Compresses the given data using the configured compression function.
        """
        return self._compress_function(data)

    def decompress(self, data: bytes) -> bytes:
        """
        Decompresses the given data using the configured decompression function.
        """
        return self._decompress_function(data)

    @property
    def compressor_import_path(self) -> str:
        """
        Returns the import path of the compression function.
        """
        return self._compress_import_path

    @property
    def decompressor_import_path(self) -> str:
        """
        Returns the import path of the decompression function.
        """
        return self._decompress_import_path


@final
class CompressorModule(Module):
    """
    Compression configuration module.
    """

    @singleton
    @provider
    def provide(self) -> Compressor:
        """
        Returns a compressor if configured, else None.
        """
        compress_path = NEXUS_FRAMEWORK_CONFIGURATION.default.remote_algorithm.compression_import_path
        decompress_path = NEXUS_FRAMEWORK_CONFIGURATION.default.remote_algorithm.decompression_import_path

        if not compress_path and not decompress_path:
            return None

        return Compressor.create(compress_path, decompress_path)


def locate_classes(pattern: re.Pattern) -> list[type[Any]]:
    """
    Locates all classes matching the pattern in the environment. Throws a start-up error if any class is not found.
    """
    classes = {
        (var_name, class_path): locate(class_path)
        for var_name, class_path in os.environ.items()
        if pattern.match(var_name)
    }

    non_located_classes = [name_and_path for name_and_path, class_ in classes.items() if class_ is None]
    if non_located_classes:
        raise FatalStartupConfigurationError(f"Failed to locate classes: {non_located_classes}")

    return list(classes.values())
