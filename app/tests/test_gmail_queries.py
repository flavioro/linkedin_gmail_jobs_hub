from app.core.config import settings
from app.infra.gmail_client import GmailClient


def test_build_relaxed_queries_are_deduped_and_do_not_include_broad_fallback():
    client = GmailClient()
    queries = client.build_relaxed_queries()

    assert queries
    assert len(queries) == len(set(queries))
    assert any("newer_than:" in query for query in queries)
    assert not any(query.startswith("linkedin ") for query in queries)


def test_build_relaxed_queries_prioritize_allowed_sender_queries_first():
    client = GmailClient()
    queries = client.build_relaxed_queries()

    assert queries[0].startswith("from:linkedin.com ")
    assert any(query.startswith("from:linkedin.com ") for query in queries)


def test_build_broad_linkedin_fallback_query():
    client = GmailClient()
    query = client.build_broad_linkedin_fallback_query()
    assert query.startswith("linkedin ")
    assert f"newer_than:{max(settings.gmail_newer_than_days, 1)}d" in query
