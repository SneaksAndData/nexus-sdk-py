from typing import final, Self

from adapta.process_communication import DataSocket
from adapta.storage.query_enabled_store import QueryEnabledStore
from adapta.storage.query_enabled_store._functions import suggest_store


@final
class QueryEnabledStoreCollection:
    """
    A container for all QES instances defined in framework configuration via respective connection strings.
    """

    def __init__(self):
        self._stores: list[QueryEnabledStore] = []

    def store_for(self, socket: DataSocket) -> QueryEnabledStore | None:
        """
        Retrieve a store for the provided socket. Usage: stores.store_for(socket).open(...).set_parameters(...).execute(...)
        """
        matching_store_type = suggest_store(socket)
        if matching_store_type is None:
            return None

        for store in self._stores:
            if isinstance(store, matching_store_type):
                return store
        return None

    def load_stores(self, store_connections: list[str]) -> Self:
        """
         Populate this collection from the configuration.
        :return:
        """
        self.close()
        self._stores.clear()

        for store_connection in store_connections:
            self._stores.append(QueryEnabledStore.from_string(store_connection))

        return self

    def close(self) -> None:
        """
         Close all stores.
        :return:
        """
        for store in self._stores:
            store.close()

    def is_empty(self) -> bool:
        """
         Check if this collection is empty.
        :return:
        """
        return len(self._stores) == 0
