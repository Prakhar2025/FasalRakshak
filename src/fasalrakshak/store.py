"""Session storage for the API.

Local development and tests use the in-memory store. On AWS (Phase 7) the
Lambda uses the DynamoDB store selected by the TABLE_SESSIONS environment
variable, so the feedback round trip survives container recycling.
"""

from __future__ import annotations

import os
from typing import Any, Protocol


class SessionStore(Protocol):
    def put(self, session_id: str, record: dict[str, Any]) -> None: ...
    def get(self, session_id: str) -> dict[str, Any] | None: ...
    def set_outcome(self, session_id: str, outcome: str) -> bool: ...


class InMemoryStore:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    def put(self, session_id: str, record: dict[str, Any]) -> None:
        self._data[session_id] = dict(record)

    def get(self, session_id: str) -> dict[str, Any] | None:
        record = self._data.get(session_id)
        return dict(record) if record is not None else None

    def set_outcome(self, session_id: str, outcome: str) -> bool:
        if session_id not in self._data:
            return False
        self._data[session_id]["outcome"] = outcome
        return True


class DynamoSessionStore:
    """Sessions in one DynamoDB table, keyed by session_id."""

    def __init__(self, table_name: str, client: Any = None) -> None:
        import boto3

        self._table_name = table_name
        self._client = client or boto3.client("dynamodb")

    def put(self, session_id: str, record: dict[str, Any]) -> None:
        self._client.put_item(
            TableName=self._table_name,
            Item={
                "session_id": {"S": session_id},
                "farmer_id": {"S": str(record.get("farmer_id", ""))},
                "status": {"S": str(record.get("status", ""))},
                "kb_entry_id": {"S": str(record.get("kb_entry_id", ""))},
                "outcome": {"S": str(record.get("outcome", "unknown"))},
            },
        )

    def get(self, session_id: str) -> dict[str, Any] | None:
        response = self._client.get_item(
            TableName=self._table_name,
            Key={"session_id": {"S": session_id}},
            ConsistentRead=True,
        )
        item = response.get("Item")
        if not item:
            return None
        return {
            "farmer_id": item.get("farmer_id", {}).get("S", ""),
            "status": item.get("status", {}).get("S", ""),
            "kb_entry_id": item.get("kb_entry_id", {}).get("S", ""),
            "outcome": item.get("outcome", {}).get("S", "unknown"),
        }

    def set_outcome(self, session_id: str, outcome: str) -> bool:
        if self.get(session_id) is None:
            return False
        self._client.update_item(
            TableName=self._table_name,
            Key={"session_id": {"S": session_id}},
            UpdateExpression="SET outcome = :outcome",
            ExpressionAttributeValues={":outcome": {"S": outcome}},
        )
        return True


def load_store() -> SessionStore:
    """Choose the store from the environment, per docs/DEPLOYMENT.md."""
    table = os.environ.get("TABLE_SESSIONS")
    if table:
        return DynamoSessionStore(table)
    return InMemoryStore()
