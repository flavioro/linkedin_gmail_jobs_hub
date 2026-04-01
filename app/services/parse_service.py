import hashlib
import json
import quopri
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup

from app.domain.enums import Seniority, WorkModel
from app.domain.schemas import JobParsed
from app.services.normalize_service import NormalizeService


class ParseService:
    MULTI_JOB_TEMPLATES = {
        "email_jobs_viewed_job_reminder_01",
        "email_jobs_saved_job_reminder_01",
        "email_application_confirmation_with_nba_01",
    }
    SINGLE_JOB_SPECIAL_TEMPLATES = {"email_job_alert_digest_01"}
    SEPARATOR_RE = re.compile(r"(?:\n|\r\n)\s*-{20,}\s*(?:\n|\r\n)")
    URL_RE = re.compile(r"https?://[^\s\">]+")

    def __init__(self) -> None:
        self.normalize_service = NormalizeService()

    def parse_many(self, *, gmail_message_id: str, headers: dict[str, str], html: str, text: str) -> list[JobParsed]:
        subject = headers.get("Subject")
        linkedin_template = headers.get("X-LinkedIn-Template")
        external_message_id = headers.get("Message-ID")
        received_at = self._parse_received_at(headers.get("Date"))
        raw_email_link = f"https://mail.google.com/mail/u/0/#inbox/{gmail_message_id}"
        body_hash = hashlib.sha256((html or text or "").encode("utf-8", errors="ignore")).hexdigest()

        jobs: list[JobParsed] = []

        if linkedin_template in self.MULTI_JOB_TEMPLATES:
            jobs.extend(
                self._parse_multi_template_from_text(
                    gmail_message_id=gmail_message_id,
                    external_message_id=external_message_id,
                    subject=subject,
                    linkedin_template=linkedin_template,
                    text=text,
                    received_at=received_at,
                    body_hash=body_hash,
                    raw_email_link=raw_email_link,
                )
            )

        if jobs:
            return jobs

        if linkedin_template in self.SINGLE_JOB_SPECIAL_TEMPLATES:
            special_single = self._parse_job_alert_digest(
                gmail_message_id=gmail_message_id,
                external_message_id=external_message_id,
                headers=headers,
                html=html,
                text=text,
                received_at=received_at,
                body_hash=body_hash,
                raw_email_link=raw_email_link,
            )
            if special_single:
                return [special_single]

        single = self._parse_single(
            gmail_message_id=gmail_message_id,
            external_message_id=external_message_id,
            headers=headers,
            html=html,
            text=text,
            received_at=received_at,
            body_hash=body_hash,
            raw_email_link=raw_email_link,
        )
        return [single] if single else []


    def parse(self, *, gmail_message_id: str, headers: dict[str, str], html: str, text: str) -> JobParsed:
        jobs = self.parse_many(gmail_message_id=gmail_message_id, headers=headers, html=html, text=text)
        if not jobs:
            raise ValueError("No jobs extracted from email.")
        return jobs[0]

    def _parse_multi_template_from_text(
        self,
        *,
        gmail_message_id: str,
        external_message_id: str | None,
        subject: str | None,
        linkedin_template: str | None,
        text: str,
        received_at: datetime | None,
        body_hash: str,
        raw_email_link: str,
    ) -> list[JobParsed]:
        normalized_text = self._normalize_text_for_plain(text)
        chunks = [c.strip() for c in self.SEPARATOR_RE.split(normalized_text) if c.strip()]
        results: list[JobParsed] = []

        parser_used_map = {
            "email_jobs_viewed_job_reminder_01": "linkedin_similar_jobs_plain_text_v1",
            "email_jobs_saved_job_reminder_01": "linkedin_saved_jobs_plain_text_v1",
            "email_application_confirmation_with_nba_01": "linkedin_application_confirmation_plain_text_v1",
        }
        parser_used = parser_used_map.get(linkedin_template, "linkedin_multi_job_plain_text_v1")

        for chunk in chunks:
            job = self._extract_job_from_chunk(
                gmail_message_id=gmail_message_id,
                external_message_id=external_message_id,
                subject=subject,
                linkedin_template=linkedin_template,
                parser_used=parser_used,
                chunk=chunk,
                received_at=received_at,
                body_hash=body_hash,
                raw_email_link=raw_email_link,
            )
            if job:
                results.append(job)

        deduped: dict[str, JobParsed] = {}
        for item in results:
            key = item.linkedin_job_id or item.linkedin_job_url or f"{item.gmail_message_id}:{item.title}"
            deduped[key] = item
        return list(deduped.values())

    def _extract_job_from_chunk(
        self,
        *,
        gmail_message_id: str,
        external_message_id: str | None,
        subject: str | None,
        linkedin_template: str | None,
        parser_used: str,
        chunk: str,
        received_at: datetime | None,
        body_hash: str,
        raw_email_link: str,
    ) -> JobParsed | None:
        lines = [self._clean_text(line) for line in chunk.splitlines() if self._clean_text(line)]
        if not lines:
            return None

        url_line = next((line for line in lines if line.lower().startswith("visualizar vaga:")), None)
        if not url_line:
            return None

        raw_url = self._clean_text(url_line.split(":", 1)[1] if ":" in url_line else "")
        normalized_url = self.normalize_service.normalize_linkedin_job_url(raw_url)
        linkedin_job_id = self.normalize_service.extract_linkedin_job_id(normalized_url or raw_url)
        if not normalized_url or not linkedin_job_id:
            return None

        url_index = lines.index(url_line)
        candidates = [line for line in lines[:url_index] if not self._is_noise_line(line)]
        if len(candidates) < 3:
            return None

        title, company, location = candidates[-3:]
        title = self._clean_title(title)
        company = self._clean_text(company)
        location = self._clean_text(location)

        if not title or len(title) > 180:
            return None
        if not company or not self._looks_like_company(company):
            return None
        if any(token in chunk.lower() for token in ["cancelar inscrição", "unsubscribe", "linkedin ireland"]):
            return None

        metadata = {
            "subject": subject,
            "from": "jobs-noreply@linkedin.com",
            "job_url_original": raw_url,
            "chunk_preview": chunk[:700],
        }
        return JobParsed(
            gmail_message_id=gmail_message_id,
            external_message_id=external_message_id,
            linkedin_job_id=linkedin_job_id,
            linkedin_job_url=normalized_url,
            raw_email_link=raw_email_link,
            email_subject=subject,
            linkedin_template=linkedin_template,
            parser_used=parser_used,
            title=title,
            company=company,
            location_raw=location,
            seniority=self._detect_seniority(" ".join(candidates)),
            work_model=self._detect_work_model(" ".join(candidates)),
            received_at=received_at,
            body_html_hash=body_hash,
            raw_metadata_json=json.dumps(metadata, ensure_ascii=False),
        )

    def _parse_job_alert_digest(
        self,
        *,
        gmail_message_id: str,
        external_message_id: str | None,
        headers: dict[str, str],
        html: str,
        text: str,
        received_at: datetime | None,
        body_hash: str,
        raw_email_link: str,
    ) -> JobParsed | None:
        subject = headers.get("Subject") or ""
        normalized_text = self._normalize_text_for_plain(text)
        job_url = self._extract_job_url(BeautifulSoup(html or "", "lxml"), normalized_text)
        normalized_url = self.normalize_service.normalize_linkedin_job_url(job_url)
        linkedin_job_id = self.normalize_service.extract_linkedin_job_id(normalized_url or job_url)
        title, company = self._extract_title_company_from_job_alert_subject(subject)
        location = self._extract_location_from_job_alert_text(normalized_text, title, company)
        combined_text = f"{subject}\n{normalized_text}"
        if not title or not linkedin_job_id:
            return None
        metadata = {
            "subject": subject,
            "from": headers.get("From"),
            "job_url_original": job_url,
            "strategy": "job_alert_digest_subject_plus_plain_text",
        }
        return JobParsed(
            gmail_message_id=gmail_message_id,
            external_message_id=external_message_id,
            linkedin_job_id=linkedin_job_id,
            linkedin_job_url=normalized_url,
            raw_email_link=raw_email_link,
            email_subject=subject,
            linkedin_template=headers.get("X-LinkedIn-Template"),
            parser_used="linkedin_job_alert_digest_v1",
            title=title,
            company=company,
            location_raw=location,
            seniority=self._detect_seniority(combined_text),
            work_model=self._detect_work_model(combined_text),
            received_at=received_at,
            body_html_hash=body_hash,
            raw_metadata_json=json.dumps(metadata, ensure_ascii=False),
        )

    def _extract_title_company_from_job_alert_subject(self, subject: str) -> tuple[str | None, str | None]:
        cleaned = self._clean_text(subject)
        patterns = [
            r"^Cargo de\s+(?P<title>.+?)\s+na\s+(?P<company>.+?)\s+e\s+outras\s+oportunidades$",
            r"^Cargo de\s+(?P<title>.+?)\s+at\s+(?P<company>.+?)\s+and\s+other\s+opportunities$",
        ]
        for pattern in patterns:
            match = re.match(pattern, cleaned, flags=re.IGNORECASE)
            if match:
                title = self._clean_title(match.group("title"))
                company = self._clean_company(match.group("company"))
                return title, company
        return self._clean_title(cleaned), None

    def _extract_location_from_job_alert_text(self, text: str, title: str | None, company: str | None) -> str | None:
        lines = [self._clean_text(line) for line in text.splitlines() if self._clean_text(line)]
        url_index = next((idx for idx, line in enumerate(lines) if line.lower().startswith("visualizar vaga:")), None)
        if url_index is None:
            return None
        window = [line for line in lines[max(0, url_index - 8):url_index] if not self._is_noise_line(line)]
        if not window:
            return None
        lowered_title = (title or "").lower()
        lowered_company = (company or "").lower()
        for line in reversed(window):
            lowered = line.lower()
            if lowered == lowered_title or lowered == lowered_company:
                continue
            if re.match(r"^\d+\s+conex(ão|ões|ao|oes)$", lowered):
                continue
            if line in {"Candidate-se com currículo e perfil", "Candidate-se agora"}:
                continue
            if self._looks_like_location(line):
                return line
        return None

    def _parse_single(
        self,
        *,
        gmail_message_id: str,
        external_message_id: str | None,
        headers: dict[str, str],
        html: str,
        text: str,
        received_at: datetime | None,
        body_hash: str,
        raw_email_link: str,
    ) -> JobParsed | None:
        soup = BeautifulSoup(html or "", "lxml")
        combined_text = self._build_combined_text(soup, text, headers)
        job_url = self._extract_job_url(soup, combined_text)
        normalized_url = self.normalize_service.normalize_linkedin_job_url(job_url)
        linkedin_job_id = self.normalize_service.extract_linkedin_job_id(normalized_url or job_url)
        title = self._extract_title(soup, combined_text, headers, normalized_url)
        company = self._extract_company(soup, combined_text, title, headers)
        location = self._extract_location(soup, combined_text)
        seniority = self._detect_seniority(combined_text)
        work_model = self._detect_work_model(combined_text)
        metadata = {
            "subject": headers.get("Subject"),
            "from": headers.get("From"),
            "job_url_original": job_url,
        }
        return JobParsed(
            gmail_message_id=gmail_message_id,
            external_message_id=external_message_id,
            linkedin_job_id=linkedin_job_id,
            linkedin_job_url=normalized_url,
            raw_email_link=raw_email_link,
            email_subject=headers.get("Subject"),
            linkedin_template=headers.get("X-LinkedIn-Template"),
            parser_used="default_html_or_text_v1",
            title=title,
            company=company,
            location_raw=location,
            seniority=seniority,
            work_model=work_model,
            received_at=received_at,
            body_html_hash=body_hash,
            raw_metadata_json=json.dumps(metadata, ensure_ascii=False),
        )

    def _normalize_text_for_plain(self, text: str) -> str:
        raw = text or ""
        raw = quopri.decodestring(raw.encode("utf-8", errors="ignore")).decode("utf-8", errors="ignore")
        raw = raw.replace("=\n", "").replace("=\r\n", "")
        return raw

    def _build_combined_text(self, soup: BeautifulSoup, text: str, headers: dict[str, str]) -> str:
        parts = []
        if headers.get("Subject"):
            parts.append(headers["Subject"])
        if soup:
            parts.append(" ".join(soup.stripped_strings))
        if text:
            parts.append(self._normalize_text_for_plain(text))
        return " ".join(part for part in parts if part)

    def _extract_title(self, soup: BeautifulSoup, combined_text: str, headers: dict[str, str], normalized_url: str | None) -> str | None:
        candidates: list[str] = []
        if headers.get("Subject"):
            candidates.extend(self._extract_title_candidates_from_subject(headers["Subject"]))
        for tag in soup.find_all(["title", "h1", "h2", "strong", "a", "span"]):
            text = self._clean_text(tag.get_text(" ", strip=True))
            if self._looks_like_job_title(text):
                candidates.append(text)
        if normalized_url:
            for tag in soup.find_all("a", href=True):
                href = self._extract_job_url_from_href(tag.get("href"))
                if href and self.normalize_service.normalize_linkedin_job_url(href) == normalized_url:
                    link_text = self._clean_text(tag.get_text(" ", strip=True))
                    if self._looks_like_job_title(link_text):
                        candidates.insert(0, link_text)
        for candidate in candidates:
            cleaned = self._clean_title(candidate)
            if cleaned:
                return cleaned
        return None

    def _extract_title_candidates_from_subject(self, subject: str) -> list[str]:
        subject = self._clean_text(subject)
        patterns = [
            r"(?:vaga|job|opportunity)[:\s-]+(.+)$",
            r"(.+?)\s+(?:na|at)\s+.+$",
        ]
        candidates = []
        if self._looks_like_job_title(subject):
            candidates.append(subject)
        for pattern in patterns:
            match = re.search(pattern, subject, flags=re.IGNORECASE)
            if match:
                candidates.append(self._clean_text(match.group(1)))
        return candidates

    def _extract_company(self, soup: BeautifulSoup, combined_text: str, title: str | None, headers: dict[str, str]) -> str | None:
        text = combined_text
        if title and " - " in title:
            tail = title.split(" - ")[-1].strip()
            if self._looks_like_company(tail):
                return tail
        subject = headers.get("Subject", "")
        if title and subject and title in subject:
            remainder = subject.replace(title, " ")
            match = re.search(r"(?:na|at)\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\w .&\-/]{1,80})", remainder, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip(" .,-")
        patterns = [
            r"(?:na empresa|empresa|company)[:\s]+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\w .&\-/]{1,80})",
            r"(?:na|at)\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\w .&\-/]{1,80})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                value = match.group(1).strip(" .,-")
                if self._looks_like_company(value):
                    return value
        return None

    def _extract_location(self, soup: BeautifulSoup, combined_text: str) -> str | None:
        patterns = [
            r"(?:local|location|cidade)[:\s]+([A-ZÁÉÍÓÚÂÊÔÃÕÇa-zà-ü ,\-/]{2,100})",
            r"([A-ZÁÉÍÓÚÂÊÔÃÕÇa-zà-ü ,\-/]{2,100})\s*[\-|–]\s*(?:remoto|híbrido|hibrido|presencial)",
            r"(?:remoto|remote|híbrido|hibrido|hybrid|presencial|onsite|on-site)\s*[\-|,:]?\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇa-zà-ü ,\-/]{2,100})",
        ]
        for pattern in patterns:
            match = re.search(pattern, combined_text, flags=re.IGNORECASE)
            if match:
                value = match.group(1).strip(" .,-")
                if len(value) >= 2:
                    return value
        return None

    def _extract_job_url(self, soup: BeautifulSoup, combined_text: str) -> str | None:
        for tag in soup.find_all("a", href=True):
            href = self._extract_job_url_from_href(tag["href"])
            if href:
                return href
        text_match = re.search(r"https?://[^\s\">]+/jobs/view/\d+/?[^\s\">]*", combined_text, flags=re.IGNORECASE)
        if text_match:
            return text_match.group(0)
        return None

    def _extract_job_url_from_href(self, href: str | None) -> str | None:
        if not href:
            return None
        raw = href.strip()
        if "/jobs/view/" in raw:
            return raw
        parsed = urlparse(raw)
        query = parse_qs(parsed.query)
        for key in ("url", "redirect", "redirectUrl", "target", "dest"):
            for value in query.get(key, []):
                decoded = unquote(value)
                if "/jobs/view/" in decoded:
                    return decoded
        return None

    def _is_noise_line(self, value: str) -> bool:
        lowered = self._clean_text(value).lower()
        if not lowered:
            return True
        exact_or_prefixes = [
            "visualizar vaga:",
            "candidate-se agora",
            "candidate-se com currículo e perfil",
            "candidate-se com curriculo e perfil",
            "candidatou-se em",
            "siga os passos a seguir",
            "veja vagas semelhantes",
            "suas outras vagas salvas",
            "ver todas as vagas salvas",
            "ver todas as vagas",
            "a vaga da ",
            "sua candidatura foi enviada",
            "você tem conexões",
            "voce tem conexoes",
            "pergunte a elas sobre a vaga",
            "enviar mensagem",
            "este e-mail foi enviado",
            "saiba por que",
            "saiba por que incluímos isso",
            "saiba por que incluimos isso",
            "cancelar inscrição",
            "cancelar inscricao",
            "ajuda:",
            "você está recebendo",
            "voce esta recebendo",
            "pesquisar outras vagas",
            "pesquisar mais vagas relacionadas",
        ]
        if any(lowered.startswith(prefix) for prefix in exact_or_prefixes):
            return True
        if re.match(r"^\d+\s+conex(ão|ões|ao|oes)$", lowered):
            return True
        if re.match(r"^[a-záéíóúâêôãõç ]+de\s+\d{1,2}\s+de\s+[a-zç]+\s+de\s+\d{4}$", lowered):
            return True
        return False

    def _detect_seniority(self, text: str) -> Seniority:
        lowered = text.lower()
        if "estágio" in lowered or "estagio" in lowered or "intern" in lowered:
            return Seniority.ESTAGIO
        if "júnior" in lowered or "junior" in lowered:
            return Seniority.JUNIOR
        if "pleno" in lowered or "mid-level" in lowered or "mid level" in lowered:
            return Seniority.PLENO
        if "sênior" in lowered or "senior" in lowered:
            return Seniority.SENIOR
        if "especialista" in lowered or "staff" in lowered or "principal" in lowered:
            return Seniority.ESPECIALISTA
        return Seniority.NAO_INFORMADO

    def _detect_work_model(self, text: str) -> WorkModel:
        lowered = text.lower()
        if "remoto" in lowered or "remote" in lowered:
            return WorkModel.REMOTO
        if "híbrido" in lowered or "hibrido" in lowered or "hybrid" in lowered:
            return WorkModel.HIBRIDO
        if "presencial" in lowered or "on-site" in lowered or "onsite" in lowered:
            return WorkModel.PRESENCIAL
        return WorkModel.NAO_INFORMADO

    def _parse_received_at(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            dt = parsedate_to_datetime(value)
            return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None

    def _looks_like_job_title(self, value: str) -> bool:
        if not value or len(value) > 180:
            return False
        lowered = value.lower()
        keywords = [
            "desenvolvedor", "developer", "engineer", "analista", "backend", "python",
            "data", "software", "full stack", "fullstack", "cientista", "qa", "devops",
        ]
        return any(keyword in lowered for keyword in keywords)

    def _looks_like_company(self, value: str) -> bool:
        if not value or len(value) > 120:
            return False
        banned = {"linkedin", "vaga", "jobs", "job", "remote work", "trabalho remoto", "outras oportunidades"}
        lowered = value.lower().strip()
        if lowered in banned:
            return False
        if re.fullmatch(r"\$?[\d,./ -]+(?:usd|brl|eur)?", lowered):
            return False
        return len(lowered.split()) <= 8

    def _looks_like_location(self, value: str) -> bool:
        lowered = self._clean_text(value).lower()
        if not lowered or len(lowered) > 120:
            return False
        banned_fragments = ["outras oportunidades", "candidate-se", "conex", "linkedin", "cargo de"]
        if any(fragment in lowered for fragment in banned_fragments):
            return False
        if re.search(r"(brasil|são paulo|sao paulo|campinas|jaguariúna|jaguariuna|remoto|remote|hybrid|híbrido|hibrido)", lowered):
            return True
        return "," in value or " - " in value

    def _clean_company(self, value: str | None) -> str | None:
        cleaned = self._clean_text(value)
        cleaned = re.sub(r"\s+e\s+outras\s+oportunidades$", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+and\s+other\s+opportunities$", "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip(" -")
        return cleaned or None

    def _clean_text(self, value: str | None) -> str:
        return " ".join((value or "").split())

    def _clean_title(self, value: str | None) -> str | None:
        cleaned = self._clean_text(value)
        cleaned = re.sub(r"^(nova\s+vaga|vaga|job|opportunity)[:\s-]+", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+(?:na|at)\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\w .&\-/]{1,80}$", "", cleaned)
        cleaned = re.sub(r"\s+via linkedin$", "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip(" -")
        return cleaned or None
