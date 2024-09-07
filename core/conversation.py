from typing import Any, Sequence

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, message_to_dict, messages_from_dict
from langchain_core.messages.ai import AIMessage
from langchain_core.messages.human import HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory

from core.db import AsyncMongoDB, MongoDB


class MongoDBChatMessageHistory(BaseChatMessageHistory):
    def __init__(
        self,
        query_id: str,
        mongo_client: AsyncMongoDB | MongoDB,
        db_name: str = None,
        collection_name: str = None,
    ):
        self._query_id = query_id
        self._client = mongo_client
        self._db_name = db_name
        self._collection_name = collection_name

        self._is_async = isinstance(mongo_client, AsyncMongoDB)

    @property
    def session_id(self) -> str:
        return self._query_id

    @property
    def messages(self) -> list[BaseMessage]:
        self._check_is_sync()
        return messages_from_dict(
            self._client.get_by_id(
                self._query_id, self._db_name, self._collection_name
            )["conversation"]
        )

    def get_messages(self) -> list[BaseMessage]:
        return self.messages

    async def aget_messages(self) -> list[BaseMessage]:
        self._check_is_async()

        result = await self._client.get_by_id(
            self._query_id, self._db_name, self._collection_name
        )
        return messages_from_dict(result["conversation"])

    def add_message(self, message: BaseMessage) -> None:
        self._check_is_sync()
        self._client.update_by_id(
            self._query_id,
            {"$push": {"conversation": message_to_dict(message)}},
            self._db_name,
            self._collection_name,
        )

    async def aadd_message(self, message: BaseMessage) -> None:
        self._check_is_async()
        await self._client.update_by_id(
            self._query_id,
            {"$push": {"conversation": message_to_dict(message)}},
            self._db_name,
            self._collection_name,
        )

    def add_messages(self, messages: Sequence[BaseMessage]) -> None:
        self._check_is_sync()
        self._client.update_by_id(
            self._query_id,
            {
                "$push": {
                    "conversation": {"$each": [message_to_dict(m) for m in messages]}
                }
            },
            self._db_name,
            self._collection_name,
        )

    async def aadd_messages(self, messages: Sequence[BaseMessage]) -> None:
        self._check_is_async()
        await self._client.update_by_id(
            self._query_id,
            {
                "$push": {
                    "conversation": {"$each": [message_to_dict(m) for m in messages]}
                }
            },
            self._db_name,
            self._collection_name,
        )

    def clear(self) -> None:
        self._check_is_sync()
        self._client.update_by_id(
            self._query_id, {"conversation": []}, self._db_name, self._collection_name
        )

    async def aclear(self) -> None:
        self._check_is_async()
        await self._client.update_by_id(
            self._query_id, {"conversation": []}, self._db_name, self._collection_name
        )

    def _check_is_async(self):
        if not self._is_async:
            raise ValueError(
                "This method is only available for AsyncMongoDB instances."
            )

    def _check_is_sync(self):
        if self._is_async:
            raise ValueError("This method is only available for MongoDB instances.")


def serialize_conversation(conversation: list[str]) -> list[dict[str, Any]]:
    """Conversation starts with Human question and then AIMessage response.
       Each time AIMessage is followed by HumanMessage. Messages are serialized
       with message_to_dict function from Lanchain and stored in a list.

    Args:
        conversation (list[str]): list with Human and AIMessage strings

    Returns:
        list[dict[str, Any]]: list with serialized messages
    """

    def to_dict(message: str, index: int) -> dict[str, Any]:
        if index % 2 == 0:
            return message_to_dict(HumanMessage(message))
        return message_to_dict(AIMessage(message))

    return [to_dict(message, index) for index, message in enumerate(conversation)]


def get_chat_history(
    session_id: str,
    mongo_client: AsyncMongoDB | MongoDB,
    db_name: str = None,
    collection_name: str = None,
) -> MongoDBChatMessageHistory:
    return MongoDBChatMessageHistory(session_id, mongo_client, db_name, collection_name)


def get_conversation_runnable(
    llm: BaseChatModel, get_session_history
) -> RunnableWithMessageHistory:
    prompt = ChatPromptTemplate.from_messages(
        [
            MessagesPlaceholder(variable_name="history"),
            ("human", "{question}"),
        ]
    )
    chain = prompt | llm
    return RunnableWithMessageHistory(
        chain,
        get_session_history,
        input_messages_key="question",
        history_messages_key="history",
    )
