from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.infra.gmail_client import GmailClient


def main() -> None:
    client = GmailClient()
    creds = client.ensure_credentials(interactive=True)
    token_path = Path(client.token_file)
    print(f"Token gerado com sucesso em: {token_path.resolve()}")
    print(f"Valido: {bool(creds and creds.valid)}")


if __name__ == "__main__":
    main()
