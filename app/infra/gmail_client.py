import base64
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.core.config import settings

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailClient:
    def __init__(self) -> None:
        self.token_file = Path(settings.google_token_file)
        self.credentials_file = Path(settings.google_credentials_file)
        self._service = None

    def ensure_credentials(self, interactive: bool = True) -> Credentials:
        creds: Credentials | None = None
        if self.token_file.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            self.token_file.write_text(creds.to_json(), encoding="utf-8")
            return creds

        if creds and creds.valid:
            return creds

        if not self.credentials_file.exists():
            raise FileNotFoundError(f"Credentials file not found: {self.credentials_file}")

        if not interactive:
            raise RuntimeError(
                "Credenciais ausentes ou invalidas e o modo interativo foi desabilitado. "
                "Execute scripts/bootstrap_gmail_token.py para gerar o token.json."
            )

        flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_file), SCOPES)
        creds = flow.run_local_server(port=0)
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        self.token_file.write_text(creds.to_json(), encoding="utf-8")
        return creds

    @property
    def service(self):
        if self._service is None:
            creds = self.ensure_credentials(interactive=True)
            self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def build_query(self, *, include_label: bool = True, include_subjects: bool = True) -> str:
        if settings.gmail_query.strip():
            return settings.gmail_query.strip()

        label = settings.gmail_label.strip()
        newer_than_days = max(settings.gmail_newer_than_days, 1)
        senders = [item.strip() for item in settings.gmail_sender_filters.split(",") if item.strip()]
        subjects = [item.strip() for item in settings.gmail_subject_terms.split(",") if item.strip()]

        parts: list[str] = []
        if include_label and label:
            parts.append(f"label:{label}")
        if senders:
            sender_query = " OR ".join(f"from:{sender}" for sender in senders)
            parts.append(f"({sender_query})")
        if include_subjects and subjects:
            subject_query = " OR ".join(f'subject:"{term}"' for term in subjects)
            parts.append(f"({subject_query})")
        parts.append(f"newer_than:{newer_than_days}d")
        return " ".join(parts)

    def build_relaxed_queries(self) -> list[str]:
        if settings.gmail_query.strip():
            return [settings.gmail_query.strip()]

        newer_than_days = max(settings.gmail_newer_than_days, 1)
        allowed_sender_fragments = [item.strip() for item in settings.allowed_sender_contains.split(",") if item.strip()]

        candidates: list[str] = []

        # Prioridade 1: restringir a busca no Gmail já na origem para remetentes permitidos.
        # Ex.: ALLOWED_SENDER_CONTAINS=linkedin.com -> from:linkedin.com newer_than:Xd
        for fragment in allowed_sender_fragments:
            candidates.append(f"from:{fragment} newer_than:{newer_than_days}d")

        # Prioridade 2: queries específicas de jobs ainda dentro do universo esperado.
        candidates.extend(
            [
                self.build_query(include_label=True, include_subjects=True),
                self.build_query(include_label=False, include_subjects=True),
                self.build_query(include_label=True, include_subjects=False),
                self.build_query(include_label=False, include_subjects=False),
            ]
        )

        deduped: list[str] = []
        for item in candidates:
            normalized = item.strip()
            if normalized and normalized not in deduped:
                deduped.append(normalized)
        return deduped

    def build_broad_linkedin_fallback_query(self) -> str:
        newer_than_days = max(settings.gmail_newer_than_days, 1)
        return f"linkedin newer_than:{newer_than_days}d"

    def list_message_ids(self, query: str | None = None, max_results: int | None = None) -> list[str]:
        effective_query = query or self.build_query()
        effective_max_results = max_results or settings.gmail_max_results

        collected: list[str] = []
        page_token: str | None = None
        while True:
            response = (
                self.service.users()
                .messages()
                .list(
                    userId=settings.gmail_user_id,
                    q=effective_query,
                    maxResults=min(100, max(1, effective_max_results - len(collected))),
                    pageToken=page_token,
                )
                .execute()
            )
            collected.extend(item["id"] for item in response.get("messages", []))
            if len(collected) >= effective_max_results:
                break
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        seen = set()
        ordered = []
        for item in collected:
            if item not in seen:
                seen.add(item)
                ordered.append(item)
        return ordered[:effective_max_results]

    def get_message(self, message_id: str) -> dict[str, Any]:
        return (
            self.service.users()
            .messages()
            .get(userId=settings.gmail_user_id, id=message_id, format="full")
            .execute()
        )

    @staticmethod
    def decode_base64url(value: str | None) -> str:
        if not value:
            return ""
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(value + padding).decode("utf-8", errors="ignore")

    def extract_bodies(self, message: dict[str, Any]) -> dict[str, str]:
        payload = message.get("payload", {})
        html_parts: list[str] = []
        text_parts: list[str] = []

        def walk(part: dict[str, Any]) -> None:
            mime_type = part.get("mimeType")
            body_data = part.get("body", {}).get("data")
            if mime_type == "text/html":
                html_parts.append(self.decode_base64url(body_data))
            elif mime_type == "text/plain":
                text_parts.append(self.decode_base64url(body_data))
            for child in part.get("parts", []):
                walk(child)

        walk(payload)
        if not html_parts and payload.get("body", {}).get("data"):
            text_parts.append(self.decode_base64url(payload["body"]["data"]))

        return {"html": "\n".join(html_parts), "text": "\n".join(text_parts)}

    @staticmethod
    def extract_headers(message: dict[str, Any]) -> dict[str, str]:
        headers = message.get("payload", {}).get("headers", [])
        return {item.get("name", ""): item.get("value", "") for item in headers}
