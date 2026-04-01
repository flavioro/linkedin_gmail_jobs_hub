from app.infra.gmail_client import GmailClient


def test_build_query_uses_refined_defaults():
    client = GmailClient()
    query = client.build_query()
    assert 'label:linkedin_jobs' in query
    assert 'from:jobs-listings@linkedin.com' in query
    assert 'subject:"vaga"' in query
    assert 'newer_than:7d' in query
