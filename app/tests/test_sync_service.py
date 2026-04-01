from app.services.sync_service import SyncService


class DummyEventsRepo:
    def create(self, **kwargs):
        return kwargs


class DummyRetryService:
    def __init__(self, results):
        self.results = results
        self.calls = 0

    def run(self, func, should_retry=None, on_retry=None):
        value = self.results[self.calls]
        self.calls += 1
        return value


def test_find_message_ids_aggregates_multiple_queries(monkeypatch):
    service = SyncService()
    monkeypatch.setattr(service.gmail_client, "build_relaxed_queries", lambda: ["q1", "q2", "q3"])
    service.retry_service = DummyRetryService([["m1", "m2"], ["m2", "m3"], []])

    query, ids = service._find_message_ids(DummyEventsRepo(), 1)

    assert query == "q3"
    assert ids == ["m1", "m2", "m3"]


def test_should_ignore_non_job_linkedin_templates():
    service = SyncService()
    headers = {"From": "LinkedIn <messaging-digest-noreply@linkedin.com>", "X-LinkedIn-Template": "email_member_message_v2", "Subject": "Tayara acabou de enviar uma mensagem a você"}
    bodies = {"text": "", "html": ""}
    allowed, reason = service._should_process_message(headers, bodies)
    assert allowed is False
    assert reason == "non_job_template"


def test_should_ignore_non_linkedin_sender_even_with_generic_query_hit():
    service = SyncService()
    headers = {"From": "Keyrus Brazil <no-reply@keyrusbrazil.teamtailor-mail.com>", "Subject": "Keyrus Brazil: uma nova vaga corresponde ao seu perfil", "X-LinkedIn-Template": ""}
    bodies = {"text": "vaga corresponde ao seu perfil", "html": ""}
    allowed, reason = service._should_process_message(headers, bodies)
    assert allowed is False
    assert reason == "unsupported_sender"


def test_should_allow_job_alert_digest_from_jobalerts_sender():
    service = SyncService()
    headers = {"From": "Alertas de vaga do LinkedIn <jobalerts-noreply@linkedin.com>", "Subject": "Cargo de Desenvolvedor Python Junior - Trabalho Remoto na BairesDev e outras oportunidades", "X-LinkedIn-Template": "email_job_alert_digest_01"}
    bodies = {"text": "Visualizar vaga: https://www.linkedin.com/comm/jobs/view/4391888310/", "html": ""}
    allowed, reason = service._should_process_message(headers, bodies)
    assert allowed is True
    assert reason == "supported_job_template"


def test_should_ignore_sender_when_allowed_sender_contains_does_not_match(monkeypatch):
    from app.core.config import settings

    service = SyncService()
    monkeypatch.setattr(settings, "allowed_sender_contains", "linkedin.com")
    headers = {"From": "Keyrus Brazil <no-reply@keyrusbrazil.teamtailor-mail.com>", "Subject": "Keyrus Brazil: uma nova vaga corresponde ao seu perfil", "X-LinkedIn-Template": "email_job_alert_digest_01"}
    bodies = {"text": "Visualizar vaga: https://www.linkedin.com/comm/jobs/view/4391888310/", "html": ""}
    allowed, reason = service._should_process_message(headers, bodies)
    assert allowed is False
    assert reason == "unsupported_sender"


class DummyEventsRepo:
    pass


def test_find_message_ids_broad_fallback_only_when_strict_queries_empty(monkeypatch):
    from app.services.sync_service import SyncService

    service = SyncService()
    monkeypatch.setattr(settings, "enable_broad_linkedin_fallback", True)
    monkeypatch.setattr(service.gmail_client, "build_relaxed_queries", lambda: ["from:linkedin.com newer_than:1d", "label:linkedin_jobs newer_than:1d"])
    monkeypatch.setattr(service.gmail_client, "build_broad_linkedin_fallback_query", lambda: "linkedin newer_than:1d")

    calls = []

    def fake_list(query, max_results):
        calls.append(query)
        if query == "linkedin newer_than:1d":
            return ["m1", "m2"]
        return []

    monkeypatch.setattr(service.gmail_client, "list_message_ids", fake_list)
    monkeypatch.setattr(service.retry_service, "run", lambda func, should_retry=None, on_retry=None: func())
    monkeypatch.setattr(service, "_event", lambda *args, **kwargs: None)
    effective_query, ids = service._find_message_ids(DummyEventsRepo(), 1)

    assert calls == ["from:linkedin.com newer_than:1d", "label:linkedin_jobs newer_than:1d", "linkedin newer_than:1d"]
    assert effective_query == "linkedin newer_than:1d"
    assert ids == ["m1", "m2"]


def test_find_message_ids_broad_fallback_disabled(monkeypatch):
    from app.services.sync_service import SyncService

    service = SyncService()
    monkeypatch.setattr(settings, "enable_broad_linkedin_fallback", False)
    monkeypatch.setattr(service.gmail_client, "build_relaxed_queries", lambda: ["from:linkedin.com newer_than:1d"])
    monkeypatch.setattr(service.gmail_client, "build_broad_linkedin_fallback_query", lambda: "linkedin newer_than:1d")

    calls = []

    def fake_list(query, max_results):
        calls.append(query)
        return []

    monkeypatch.setattr(service.gmail_client, "list_message_ids", fake_list)
    monkeypatch.setattr(service.retry_service, "run", lambda func, should_retry=None, on_retry=None: func())
    monkeypatch.setattr(service, "_event", lambda *args, **kwargs: None)
    effective_query, ids = service._find_message_ids(DummyEventsRepo(), 1)

    assert calls == ["from:linkedin.com newer_than:1d"]
    assert effective_query == "from:linkedin.com newer_than:1d"
    assert ids == []


def test_find_message_ids_skips_broad_fallback_when_strict_queries_return_results(monkeypatch):
    from app.services.sync_service import SyncService

    service = SyncService()
    monkeypatch.setattr(settings, "enable_broad_linkedin_fallback", True)
    monkeypatch.setattr(service.gmail_client, "build_relaxed_queries", lambda: ["from:linkedin.com newer_than:1d", "label:linkedin_jobs newer_than:1d"])
    monkeypatch.setattr(service.gmail_client, "build_broad_linkedin_fallback_query", lambda: "linkedin newer_than:1d")

    calls = []

    def fake_list(query, max_results):
        calls.append(query)
        if query == "from:linkedin.com newer_than:1d":
            return ["m1"]
        return ["m2"]

    monkeypatch.setattr(service.gmail_client, "list_message_ids", fake_list)
    monkeypatch.setattr(service.retry_service, "run", lambda func, should_retry=None, on_retry=None: func())
    monkeypatch.setattr(service, "_event", lambda *args, **kwargs: None)
    effective_query, ids = service._find_message_ids(DummyEventsRepo(), 1)

    assert calls == ["from:linkedin.com newer_than:1d", "label:linkedin_jobs newer_than:1d"]
    assert effective_query == "label:linkedin_jobs newer_than:1d"
    assert ids == ["m1", "m2"]
