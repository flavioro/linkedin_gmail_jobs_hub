from __future__ import annotations

import socket
from typing import Any

from googleapiclient.errors import HttpError
from httplib2.error import ServerNotFoundError
from sqlalchemy.exc import IntegrityError, PendingRollbackError, SQLAlchemyError


class ErrorService:
    TRANSIENT_HTTP_STATUSES = {408, 425, 429, 500, 502, 503, 504}

    def classify(self, exc: Exception) -> str:
        if isinstance(exc, ServerNotFoundError):
            return "network_dns_error"
        if isinstance(exc, socket.gaierror):
            return "network_dns_error"
        if isinstance(exc, socket.timeout | TimeoutError):
            return "network_timeout"
        if isinstance(exc, ConnectionError):
            return "network_connection_error"
        if isinstance(exc, HttpError):
            status = getattr(exc.resp, "status", None)
            if status == 401:
                return "gmail_auth_error"
            if status == 403:
                return "gmail_permission_error"
            if status == 429:
                return "gmail_rate_limit"
            if status and 500 <= status <= 599:
                return "gmail_server_error"
            return "gmail_api_error"
        if isinstance(exc, IntegrityError):
            return "db_integrity_error"
        if isinstance(exc, PendingRollbackError | SQLAlchemyError):
            return "db_transaction_error"
        if isinstance(exc, ValueError):
            return "parser_error"
        return "unknown_error"

    def is_transient(self, exc: Exception) -> bool:
        if isinstance(exc, (ServerNotFoundError, socket.gaierror, socket.timeout, TimeoutError, ConnectionError)):
            return True
        if isinstance(exc, HttpError):
            status = getattr(exc.resp, "status", None)
            return bool(status in self.TRANSIENT_HTTP_STATUSES)
        return False

    def summarize(self, exc: Exception) -> str:
        return f"{self.classify(exc)}: {str(exc)}"[:1000]

    def status_code(self, exc: Exception) -> int | None:
        if isinstance(exc, HttpError):
            return getattr(exc.resp, "status", None)
        return None

    def payload(self, exc: Exception) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error_type": type(exc).__name__,
            "error_summary": self.classify(exc),
            "message": str(exc)[:1000],
        }
        status = self.status_code(exc)
        if status is not None:
            payload["status_code"] = status
        return payload
