from dataclasses import dataclass
from pydoc import locate
from typing import final, Self


@final
@dataclass
class NexusErrorMap:
    """
    Remapped exception definition
    """

    target: type[BaseException]
    errors: list[type[BaseException]]

    def map_exception(self, ex: BaseException) -> type[BaseException] | None:
        """
        Try to map an exception using internal errors list.
        """
        # empty list means default remap for any exception
        if len(self.errors) == 0:
            return self.target

        for source_error in self.errors:
            if isinstance(ex, source_error):
                return self.target

        return None

    @classmethod
    def from_config(cls, value: dict) -> Self:
        """
         Creates an instance of NexusErrorMap from the provided dictionary.
        :param value:
        :return:
        """
        target: type[BaseException] = locate(value["target"])
        errors: list[type[BaseException]] = list(map(locate, value["errors"]))

        return cls(target, errors)


@final
class NexusErrorMapCollection:
    """
    Error map for Fatal/Transient Nexus errors
    """

    def __init__(self, global_default: type[BaseException], error_map: dict[str, list[NexusErrorMap]]) -> None:
        self._global_default = global_default
        self._error_map = error_map or {}

    def map_error(self, ex: BaseException, caller: type) -> type[BaseException]:
        """
         Map a provided exception to a different one, using the configured collection.
        :param ex: Error to be mapped
        :param caller: __class__ attribute of the caller instance
        """

        def _get_caller_fqn() -> str:
            return f"{caller.__module__}.{caller.__qualname__}"

        caller_fqn = _get_caller_fqn()
        if caller_fqn in self._error_map:
            for error_map_entry in self._error_map[caller_fqn]:
                mapped_ex = error_map_entry.map_exception(ex)
                if mapped_ex:
                    return mapped_ex

        return self._global_default
