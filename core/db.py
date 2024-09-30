import os
from typing import Any, Dict, List, Protocol

from bson.objectid import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient, UpdateOne


class Database(Protocol):
    def get(self, key: str) -> Any: ...

    def get_by_id(self, id: str) -> Any: ...

    def insert(self, key: str, value: Any) -> None: ...

    def insert_bulk(self, data: dict[str, Any]) -> None: ...

    def update_by_id(self, id: str, update_ops: dict[str, Any]) -> None: ...

    def update(self, key: str, value: Any) -> None: ...

    def update_bulk(self, data: dict[str, Any]) -> None: ...


class MongoClientMixin:
    _client: MongoClient | AsyncIOMotorClient = None
    _default_db = None
    _default_collection = None

    def __del__(self):
        self._client.close()

    def _get_collection(
        self, database: str | None = None, collection: str | None = None
    ) -> Any:
        if collection is None:
            return self._default_collection
        if database is None:
            return self._default_db[collection]
        return self._client[database][collection]


class MongoDB(MongoClientMixin):
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

    def get(
        self, key: str, database: str | None = None, collection: str | None = None
    ) -> Any:
        collection = self._get_collection(database, collection)
        return collection.find_one({key: key})

    def get_by_id(
        self, id: str, database: str | None = None, collection: str | None = None
    ) -> Any:
        collection = self._get_collection(database, collection)
        return collection.find_one({"_id": ObjectId(id)})

    def insert(
        self,
        data: Dict[str, Any],
        database: str | None = None,
        collection: str | None = None,
    ):
        collection = self._get_collection(database, collection)
        return collection.insert_one(data)

    def insert_bulk(
        self,
        data: List[Dict[str, Any]],
        database: str | None = None,
        collection: str | None = None,
    ):
        collection = self._get_collection(database, collection)
        return collection.insert_many(data)

    def update_by_id(
        self,
        id: str,
        update_ops: Dict[str, Any],
        database: str | None = None,
        collection: str | None = None,
        upsert: bool = False,
    ) -> None:
        collection = self._get_collection(database, collection)
        collection.update_one({"_id": ObjectId(id)}, update_ops, upsert=upsert)

    def update(
        self,
        key: Dict[str, Any],
        update_ops: Dict[str, Any],
        database: str | None = None,
        collection: str | None = None,
        upsert: bool = False,
    ) -> None:
        collection = self._get_collection(database, collection)
        collection.update_one(key, update_ops, upsert=upsert)

    def update_bulk(
        self,
        update_key: str,
        data: List[Dict[str, Any]],
        database: str | None = None,
        collection: str | None = None,
        upsert: bool = False,
    ) -> None:
        collection = self._get_collection(database, collection)

        operations = []
        for entry in data:
            operations.append(
                UpdateOne(
                    {update_key: entry[update_key]},
                    {"$set": entry},
                    upsert=upsert,
                )
            )
        collection.bulk_write(operations)

    def delete(
        self,
        key: Dict[str, Any],
        database: str | None = None,
        collection: str | None = None,
    ) -> None:
        collection = self._get_collection(database, collection)
        collection.delete_one(key)


class AsyncMongoDB(MongoClientMixin):
    def __init__(
        self,
        host: str,
        default_db: str,
        default_collection: str,
        username: str | None = None,
        password: str | None = None,
    ):
        self._client = AsyncIOMotorClient(
            host,
            username=username,
            password=password,
            authSource="admin",
        )
        self._default_db = self._client[default_db]
        self._default_collection = self._default_db[default_collection]

    async def get(
        self,
        key: Dict[str, Any],
        database: str | None = None,
        collection: str | None = None,
    ) -> Any:
        collection = self._get_collection(database, collection)
        return await collection.find_one(key)

    async def get_by_id(
        self, id: str, database: str | None = None, collection: str | None = None
    ) -> Any:
        collection = self._get_collection(database, collection)
        return await collection.find_one({"_id": ObjectId(id)})

    async def insert(
        self,
        data: Dict[str, Any],
        database: str | None = None,
        collection: str | None = None,
    ) -> None:
        collection = self._get_collection(database, collection)
        return await collection.insert_one(data)

    async def insert_bulk(
        self,
        data: List[Dict[str, Any]],
        database: str | None = None,
        collection: str | None = None,
    ) -> None:
        collection = self._get_collection(database, collection)
        return await collection.insert_many(data)

    async def update_by_id(
        self,
        id: str,
        update_ops: Dict[str, Any],
        database: str | None = None,
        collection: str | None = None,
        upsert: bool = False,
    ) -> None:
        collection = self._get_collection(database, collection)
        return await collection.update_one({"_id": ObjectId(id)}, update_ops, upsert=upsert)

    async def update(
        self,
        key: Dict[str, Any],
        update_ops: Dict[str, Any],
        database: str | None = None,
        collection: str | None = None,
        upsert: bool = False,
    ):
        collection = self._get_collection(database, collection)
        return await collection.update_one(key, update_ops, upsert=upsert)

    async def update_bulk(
        self,
        update_key: str,
        data: List[Dict[str, Any]],
        database: str | None = None,
        collection: str | None = None,
        upsert: bool = False,
    ):
        collection = self._get_collection(database, collection)

        operations = []
        for entry in data:
            operations.append(
                UpdateOne(
                    {update_key: entry[update_key]},
                    {"$set": entry},
                    upsert=upsert,
                )
            )
        return await collection.bulk_write(operations)

    async def delete(
        self,
        key: Dict[str, Any],
        database: str | None = None,
        collection: str | None = None,
    ) -> None:
        collection = self._get_collection(database, collection)
        await collection.delete_one(key)


def init_mongo_db_instance(
    is_async: bool = True,
    default_db: str | None = None,
    default_collection: str | None = None,
) -> MongoDB | AsyncMongoDB:
    mongo_host = os.getenv("MONGODB_HOST", "mongodb")
    mongo_port = os.getenv("MONGODB_PORT", 27017)
    host = f"mongodb://{mongo_host}:{mongo_port}/"

    settings = {
        "host": host,
        "default_db": default_db,
        "default_collection": default_collection,
        "username": os.getenv("MONGODB_ADMIN_USER"),
        "password": os.getenv("MONGODB_ADMIN_PASS"),
    }
    if is_async:
        return AsyncMongoDB(**settings)
    return MongoDB(**settings)
