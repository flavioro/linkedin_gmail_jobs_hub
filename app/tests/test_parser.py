from pathlib import Path

from app.services.parse_service import ParseService


def test_parse_linkedin_html_sample():
    html = Path("app/tests/fixtures/linkedin_email_sample.html").read_text(encoding="utf-8")
    service = ParseService()
    parsed = service.parse(
        gmail_message_id="abc123",
        headers={"Subject": "Nova vaga", "From": "jobs-listings@linkedin.com", "Date": "Tue, 01 Apr 2026 10:00:00 +0000"},
        html=html,
        text="",
    )
    assert parsed.linkedin_job_id == "4392930380"
    assert parsed.linkedin_job_url == "https://linkedin.com/comm/jobs/view/4392930380/"
    assert parsed.title == "Desenvolvedor Python Pleno - Empresa Exemplo"
    assert parsed.company == "Empresa Exemplo"
    assert parsed.work_model.value == "hibrido"


def test_parse_redirect_job_link_and_subject_variation():
    html = Path("app/tests/fixtures/linkedin_email_redirect_sample.html").read_text(encoding="utf-8")
    service = ParseService()
    parsed = service.parse(
        gmail_message_id="xyz999",
        headers={
            "Subject": "Vaga: Backend Python Júnior na ACME Tech",
            "From": "jobs-listings@linkedin.com",
            "Date": "Tue, 01 Apr 2026 10:00:00 +0000",
        },
        html=html,
        text="",
    )
    assert parsed.linkedin_job_id == "4400000001"
    assert parsed.linkedin_job_url == "https://linkedin.com/jobs/view/4400000001/"
    assert parsed.title == "Backend Python Júnior"
    assert parsed.company == "ACME Tech"
    assert parsed.work_model.value == "remoto"


from email import policy
from email.parser import BytesParser


def test_parse_many_from_real_linkedin_eml_fixture():
    eml_bytes = Path("app/tests/fixtures/linkedin_multi_jobs.eml").read_bytes()
    message = BytesParser(policy=policy.default).parsebytes(eml_bytes)

    text_body = message.get_body(preferencelist=("plain",))
    html_body = message.get_body(preferencelist=("html",))

    headers = {
        "Subject": message.get("Subject", ""),
        "From": message.get("From", ""),
        "Date": message.get("Date", ""),
        "Message-ID": message.get("Message-ID", ""),
        "X-LinkedIn-Template": message.get("X-LinkedIn-Template", ""),
    }

    service = ParseService()
    jobs = service.parse_many(
        gmail_message_id="fixture-message-id",
        headers=headers,
        html=html_body.get_content() if html_body else "",
        text=text_body.get_content() if text_body else "",
    )

    assert len(jobs) == 9
    job_ids = {job.linkedin_job_id for job in jobs}
    assert "4392930380" in job_ids
    assert "4391875466" in job_ids
    assert "4391894007" in job_ids
    assert all(job.gmail_message_id == "fixture-message-id" for job in jobs)
    assert all(job.linkedin_template == "email_jobs_viewed_job_reminder_01" for job in jobs)


def test_parse_many_from_saved_jobs_reminder_eml_fixture():
    eml_bytes = Path("app/tests/fixtures/linkedin_saved_jobs_reminder.eml").read_bytes()
    message = BytesParser(policy=policy.default).parsebytes(eml_bytes)

    text_body = message.get_body(preferencelist=("plain",))
    html_body = message.get_body(preferencelist=("html",))

    headers = {
        "Subject": message.get("Subject", ""),
        "From": message.get("From", ""),
        "Date": message.get("Date", ""),
        "Message-ID": message.get("Message-ID", ""),
        "X-LinkedIn-Template": message.get("X-LinkedIn-Template", ""),
    }

    service = ParseService()
    jobs = service.parse_many(
        gmail_message_id="saved-message-id",
        headers=headers,
        html=html_body.get_content() if html_body else "",
        text=text_body.get_content() if text_body else "",
    )

    assert len(jobs) == 4
    assert {job.linkedin_job_id for job in jobs} == {"4369584745", "4377993920", "4389819829", "4378623672"}
    assert all(job.linkedin_template == "email_jobs_saved_job_reminder_01" for job in jobs)
    assert all(job.parser_used == "linkedin_saved_jobs_plain_text_v1" for job in jobs)


def test_parse_many_from_application_confirmation_eml_fixture():
    eml_bytes = Path("app/tests/fixtures/linkedin_application_confirmation.eml").read_bytes()
    message = BytesParser(policy=policy.default).parsebytes(eml_bytes)

    text_body = message.get_body(preferencelist=("plain",))
    html_body = message.get_body(preferencelist=("html",))

    headers = {
        "Subject": message.get("Subject", ""),
        "From": message.get("From", ""),
        "Date": message.get("Date", ""),
        "Message-ID": message.get("Message-ID", ""),
        "X-LinkedIn-Template": message.get("X-LinkedIn-Template", ""),
    }

    service = ParseService()
    jobs = service.parse_many(
        gmail_message_id="application-message-id",
        headers=headers,
        html=html_body.get_content() if html_body else "",
        text=text_body.get_content() if text_body else "",
    )

    assert len(jobs) == 4
    assert {job.linkedin_job_id for job in jobs} == {"4385054128", "4395160653", "4388591312", "4392680569"}
    assert any(job.title == "SUPORTE JUNIOR I" for job in jobs)
    assert all(job.linkedin_template == "email_application_confirmation_with_nba_01" for job in jobs)
    assert all(job.parser_used == "linkedin_application_confirmation_plain_text_v1" for job in jobs)
    easy_apply_by_id = {job.linkedin_job_id: job.is_easy_apply for job in jobs}
    assert easy_apply_by_id["4385054128"] is False
    assert easy_apply_by_id["4395160653"] is False
    assert easy_apply_by_id["4388591312"] is True
    assert easy_apply_by_id["4392680569"] is True


import pytest


@pytest.mark.parametrize(
    ("subject", "expected_title", "expected_company", "expected_location"),
    [
        (
            "Cargo de Desenvolvedor Python Junior - Trabalho Remoto na BairesDev e outras oportunidades",
            "Desenvolvedor Python Junior - Trabalho Remoto",
            "BairesDev",
            "Brasil",
        ),
        (
            "Cargo de Intermediate Software Engineer (Python) - OP02093 na Dev.Pro e outras oportunidades",
            "Intermediate Software Engineer (Python) - OP02093",
            "Dev.Pro",
            "Brasil",
        ),
        (
            "Cargo de Artificial Intelligence Engineer, LearnWith.AI (Remote) - $200,000/year USD na Crossover e outras oportunidades",
            "Artificial Intelligence Engineer, LearnWith.AI (Remote) - $200,000/year USD",
            "Crossover",
            "COM INGLÊS",
        ),
    ],
)
def test_parse_job_alert_digest_subject_and_plain_text(subject, expected_title, expected_company, expected_location):
    service = ParseService()
    headers = {
        "Subject": subject,
        "From": "Alertas de vaga do LinkedIn <jobalerts-noreply@linkedin.com>",
        "Date": "Tue, 01 Apr 2026 10:00:00 +0000",
        "Message-ID": "<test@example.com>",
        "X-LinkedIn-Template": "email_job_alert_digest_01",
    }
    text = f"""{expected_title}
{expected_company}
{expected_location}
Visualizar vaga: https://www.linkedin.com/comm/jobs/view/4391888310/?trackingId=abc
"""
    jobs = service.parse_many(gmail_message_id="digest-1", headers=headers, html="", text=text)
    assert len(jobs) == 1
    parsed = jobs[0]
    assert parsed.parser_used == "linkedin_job_alert_digest_v1"
    assert parsed.title == expected_title
    assert parsed.company == expected_company
    assert parsed.location_raw == expected_location
    assert parsed.linkedin_job_id == "4391888310"
