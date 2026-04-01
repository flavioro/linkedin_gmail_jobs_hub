import re
from urllib.parse import urlparse, urlunparse


class NormalizeService:
    JOB_ID_PATTERN = re.compile(r"/jobs/view/(\d+)/?")

    def normalize_linkedin_job_url(self, url: str | None) -> str | None:
        if not url:
            return None
        parsed = urlparse(url.strip())
        netloc = parsed.netloc.lower().replace("www.", "")
        path = parsed.path.rstrip("/")
        if path:
            path = f"{path}/"
        normalized = parsed._replace(scheme="https", netloc=netloc, path=path, query="", fragment="")
        return urlunparse(normalized)

    def extract_linkedin_job_id(self, url: str | None) -> str | None:
        if not url:
            return None
        match = self.JOB_ID_PATTERN.search(url)
        return match.group(1) if match else None
