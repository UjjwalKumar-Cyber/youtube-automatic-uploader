import argparse
import csv
import json
import mimetypes
import os
import pickle
import smtplib
import time
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from openai import OpenAI
from tqdm import tqdm


BASE_DIR = Path(__file__).resolve().parent
VIDEOS_FOLDER = BASE_DIR / "videos"
CSV_FILE = BASE_DIR / "uploads.csv"
LOG_FILE = BASE_DIR / "upload_log.csv"
CLIENT_SECRET_FILE = BASE_DIR / "client_secret.json"
TOKEN_FILE = BASE_DIR / "youtube_token.pickle"

MAX_RETRIES = 3
DELAY_BETWEEN_UPLOADS = 20
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
EMAIL_FROM = os.getenv("EMAIL_FROM", "")
EMAIL_TO = os.getenv("EMAIL_TO", EMAIL_FROM)
EMAIL_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def load_uploads():
    if not CSV_FILE.exists():
        raise FileNotFoundError(f"Missing CSV file: {CSV_FILE}")

    uploads = []
    with CSV_FILE.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if "filename" not in (reader.fieldnames or []):
            raise ValueError("uploads.csv must contain a filename column")

        for row in reader:
            filename = row.get("filename", "").strip()
            if not filename or filename.startswith("#"):
                continue

            uploads.append(
                {
                    "filename": filename,
                    "title": row.get("title", "").strip(),
                    "description": row.get("description", "").strip(),
                    "tags": [t.strip() for t in row.get("tags", "").split(",") if t.strip()],
                    "privacy": (row.get("privacy", "private").strip().lower() or "private"),
                    "publish_at": row.get("publish_at", "").strip() or None,
                    "thumbnail": row.get("thumbnail", "").strip() or None,
                    "topic": row.get("topic", "").strip(),
                }
            )
    return uploads


def load_log():
    log = {}
    if LOG_FILE.exists():
        with LOG_FILE.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                log[row["filename"]] = row
    return log


def save_log_entry(entry):
    file_exists = LOG_FILE.exists()
    fieldnames = ["filename", "title", "video_id", "status", "timestamp", "error"]
    with LOG_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow({key: entry.get(key, "") for key in fieldnames})


def generate_ai_metadata(topic, filename):
    if not client or not topic:
        return None, None

    try:
        prompt = f"""Generate a catchy, SEO-optimized YouTube title and a detailed, engaging description.
Filename: {filename}
Topic: {topic}

Return exactly in this format:
TITLE: [title here]
DESCRIPTION: [full description here]"""
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.75,
            max_tokens=900,
        )
        text = response.choices[0].message.content.strip()
        if "TITLE:" not in text or "DESCRIPTION:" not in text:
            return None, None
        title = text.split("TITLE:", 1)[1].split("DESCRIPTION:", 1)[0].strip()
        description = text.split("DESCRIPTION:", 1)[1].strip()
        return title, description
    except Exception as e:
        print(f"AI generation failed for {filename}: {e}")
        return None, None


def ensure_metadata(row):
    if (not row["title"] or not row["description"]) and row["topic"]:
        title, description = generate_ai_metadata(row["topic"], row["filename"])
        if title and description:
            row["title"] = title
            row["description"] = description
            print("   AI generated title and description")

    if not row["title"]:
        row["title"] = Path(row["filename"]).stem.replace("_", " ").title()
    if not row["description"]:
        row["description"] = row["title"]
    return row


def resolve_path(path_value):
    if not path_value:
        return None
    path = Path(path_value)
    return path if path.is_absolute() else BASE_DIR / path


def normalize_publish_at(value):
    if not value:
        return None

    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.isoformat()


def get_youtube_service():
    if not CLIENT_SECRET_FILE.exists():
        raise FileNotFoundError(
            f"Missing {CLIENT_SECRET_FILE.name}. Download OAuth Desktop client credentials "
            "from Google Cloud Console and save them here."
        )

    credentials = None
    if TOKEN_FILE.exists():
        with TOKEN_FILE.open("rb") as token:
            credentials = pickle.load(token)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), SCOPES)
            credentials = flow.run_local_server(port=0)

        with TOKEN_FILE.open("wb") as token:
            pickle.dump(credentials, token)

    return build("youtube", "v3", credentials=credentials)


def upload_video(youtube, row, force=False):
    row = ensure_metadata(row)
    video_path = VIDEOS_FOLDER / row["filename"]
    if not video_path.exists():
        return {"status": "failed", "error": f"Video not found: {video_path}"}

    log = load_log()
    if row["filename"] in log and log[row["filename"]].get("status") == "success" and not force:
        print("   Skipped because it was already uploaded successfully")
        return {"status": "skipped", "video_id": log[row["filename"]].get("video_id", ""), "error": ""}

    privacy = row["privacy"]
    publish_at = normalize_publish_at(row["publish_at"])
    if publish_at:
        privacy = "private"

    body = {
        "snippet": {
            "title": row["title"],
            "description": row["description"],
            "tags": row["tags"],
            "categoryId": "24",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
            **({"publishAt": publish_at} if publish_at else {}),
        },
    }

    media_type = mimetypes.guess_type(video_path)[0] or "video/*"
    media = MediaFileUpload(str(video_path), mimetype=media_type, chunksize=8 * 1024 * 1024, resumable=True)

    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    last_error = ""

    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                print(f"   Upload progress: {int(status.progress() * 100)}%")
        except HttpError as e:
            last_error = str(e)
            if e.resp.status not in [500, 502, 503, 504]:
                return {"status": "failed", "error": last_error}
            raise

    video_id = response.get("id", "")

    thumbnail = resolve_path(row["thumbnail"])
    if thumbnail and thumbnail.exists():
        youtube.thumbnails().set(videoId=video_id, media_body=str(thumbnail)).execute()
    elif row["thumbnail"]:
        print(f"   Thumbnail not found, continuing without it: {thumbnail}")

    return {"status": "success", "video_id": video_id, "error": last_error}


def upload_with_retries(youtube, row, force=False):
    last_error = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return upload_video(youtube, row, force=force)
        except Exception as e:
            last_error = str(e)
            print(f"   Attempt {attempt} failed: {last_error}")
            if attempt < MAX_RETRIES:
                time.sleep(attempt * 40)
    return {"status": "failed", "video_id": "", "error": last_error or "Max retries exceeded"}


def send_email_summary(results):
    if not EMAIL_FROM or not EMAIL_TO or not EMAIL_PASSWORD:
        return

    success = sum(1 for r in results if r["status"] == "success")
    body = f"YouTube Batch Upload Finished!\n\nTotal: {len(results)}\nSuccessful: {success}\n\n"
    for result in results:
        body += f"{result['status'].upper()}: {result['filename']} -> {result.get('video_id') or result.get('error', '')}\n"

    msg = MIMEText(body)
    msg["Subject"] = f"YouTube Upload Complete - {success}/{len(results)} uploaded"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())


def main():
    parser = argparse.ArgumentParser(description="Official YouTube Data API batch uploader")
    parser.add_argument("--force", action="store_true", help="Re-upload successful videos")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, do not upload")
    args = parser.parse_args()

    print("YouTube Data API Batch Uploader\n")
    uploads = load_uploads()

    if args.dry_run:
        for row in uploads:
            video_path = VIDEOS_FOLDER / row["filename"]
            thumbnail = resolve_path(row["thumbnail"])
            thumb_status = "no thumbnail"
            if thumbnail:
                thumb_status = "thumbnail ready" if thumbnail.exists() else "thumbnail missing"
            status = "ready" if video_path.exists() else "missing video"
            print(f"{row['filename']}: {status}; {thumb_status}; privacy={row['privacy']}")
        return

    youtube = get_youtube_service()
    results = []
    for row in tqdm(uploads, desc="Processing videos", unit="video"):
        print(f"\n{row['filename']}")
        result = upload_with_retries(youtube, row, force=args.force)
        entry = {
            "filename": row["filename"],
            "title": row["title"],
            "video_id": result.get("video_id", ""),
            "status": result.get("status", ""),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "error": result.get("error", ""),
        }
        if result.get("status") != "skipped":
            save_log_entry(entry)
        results.append(entry)
        if result.get("status") == "success":
            time.sleep(DELAY_BETWEEN_UPLOADS)

    send_email_summary(results)
    print("\nDone. Check upload_log.csv for results.")


if __name__ == "__main__":
    main()
