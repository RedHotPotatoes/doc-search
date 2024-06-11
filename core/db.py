from typing import Any, Dict, List, Protocol

from pretty_logging import with_logger
from pymongo import MongoClient


class Database(Protocol):
    def get(self, key: str) -> Any: ...

    def insert(self, key: str, value: Any) -> None: ...

    def insert_bulk(self, data: dict[str, Any]) -> None: ...


@with_logger
class MongoDB:
    def __init__(
        self,
        host: str,
        default_db: str,
        default_collection: str,
        username: str | None = None,
        password: str | None = None,
    ):
        self._client = MongoClient(
            host,
            username=username,
            password=password,
            authSource="admin",
        )
        self._default_db = self._client[default_db]
        self._default_collection = self._default_db[default_collection]

    def __del__(self):
        self._client.close()

    def get(
        self, key: str, database: str | None = None, collection: str | None = None
    ) -> Any:
        raise NotImplementedError

    def insert(
        self,
        data: Dict[str, Any],
        database: str | None = None,
        collection: str | None = None,
    ) -> None:
        collection = self._get_collection(database, collection)
        collection.insert_one(data)

    def insert_bulk(
        self,
        data: List[Dict[str, Any]],
        database: str | None = None,
        collection: str | None = None,
    ) -> None:
        collection = self._get_collection(database, collection)
        collection.insert_many(data)

    def _get_collection(
        self, database: str | None = None, collection: str | None = None
    ) -> Any:
        if collection is None:
            return self._default_collection
        if database is None:
            return self._default_db[collection]
        return self._client[database][collection]
