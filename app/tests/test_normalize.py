from app.services.normalize_service import NormalizeService


def test_normalize_linkedin_job_url_removes_query_and_keeps_trailing_slash():
    service = NormalizeService()
    raw = "https://www.linkedin.com/comm/jobs/view/4392930380/?trackingId=abc&trk=x"
    assert service.normalize_linkedin_job_url(raw) == "https://linkedin.com/comm/jobs/view/4392930380/"


def test_extract_linkedin_job_id():
    service = NormalizeService()
    url = "https://linkedin.com/comm/jobs/view/4392930380/"
    assert service.extract_linkedin_job_id(url) == "4392930380"
