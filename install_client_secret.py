import json
import shutil
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
TARGET = BASE_DIR / "client_secret.json"
DOWNLOADS = Path.home() / "Downloads"


def looks_like_oauth_secret(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False

    section = data.get("installed") or data.get("web")
    if not section:
        return False

    return all(section.get(key) for key in ["client_id", "client_secret", "auth_uri", "token_uri"])


def main():
    candidates = sorted(
        DOWNLOADS.glob("client_secret*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    candidates += sorted(
        DOWNLOADS.glob("*.apps.googleusercontent.com.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    for candidate in candidates:
        if looks_like_oauth_secret(candidate):
            shutil.copy2(candidate, TARGET)
            print(f"Copied OAuth credentials to: {TARGET}")
            print("Now run: python batch_upload_api.py")
            return

    print("No Google OAuth client JSON found in Downloads.")
    print("Download the Desktop app OAuth JSON from Google Cloud, then run this script again.")


if __name__ == "__main__":
    main()
