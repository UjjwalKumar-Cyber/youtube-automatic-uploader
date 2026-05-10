# YouTube Automatic Uploader

Reusable batch uploader for YouTube videos using the official YouTube Data API.

Created by **Ujjwal Kumar**, CSE student.

## Features

- Batch uploads from one `uploads.csv`
- Official Google OAuth login
- Private, public, and unlisted uploads
- Scheduled publishing with `publish_at`
- Optional thumbnail upload
- AI title and description generation with OpenAI
- Resume support using `upload_log.csv`
- Retries with backoff
- Dry-run mode
- Optional email summary

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create folders:

```bash
mkdir -p videos thumbnails
cp uploads.example.csv uploads.csv
```

Put videos inside `videos/`, optional thumbnails inside `thumbnails/`, then edit `uploads.csv`.

Or use the interactive helper so you do not need to edit CSV manually.

## Google OAuth Setup

1. Create a Google Cloud project.
2. Enable **YouTube Data API v3**.
3. Configure OAuth consent screen as **External**.
4. Add your Google account as a test user.
5. Create OAuth client credentials for **Desktop app**.
6. Download the JSON file.
7. Place it in this project folder as `client_secret.json`.

If it downloaded to your Downloads folder, run:

```bash
python install_client_secret.py
```

## CSV Format

```csv
filename,title,description,tags,privacy,publish_at,thumbnail,topic
example_video.mp4,My Title,My description,"tag1,tag2",private,,,
scheduled_video.mp4,,, "tag1,tag2",private,2026-05-20T15:00:00,thumbnails/thumb1.jpg,Video topic for AI
```

Columns:

- `filename`: video filename inside `videos/`
- `title`: YouTube title
- `description`: YouTube description
- `tags`: comma-separated tags, wrapped in quotes
- `privacy`: `private`, `public`, or `unlisted`
- `publish_at`: optional ISO date/time, for example `2026-05-20T15:00:00`
- `thumbnail`: optional thumbnail path
- `topic`: used for AI metadata if title or description is blank

## Run

Save your common defaults once:

```bash
python batch_upload_api.py --setup
```

This creates `uploader_config.json` locally with defaults such as privacy, default tags, default description, scheduling behavior, and thumbnail folder.

After adding videos to `videos/`, ask for upload details one by one:

```bash
python batch_upload_api.py --add-videos
```

This creates or updates `uploads.csv` for new videos only.

To re-edit videos already listed in `uploads.csv`:

```bash
python batch_upload_api.py --add-videos --edit-existing
```

Preview only:

```bash
python batch_upload_api.py --dry-run
```

Upload:

```bash
python batch_upload_api.py
```

Force re-upload videos already marked successful:

```bash
python batch_upload_api.py --force
```

## Optional OpenAI Metadata

```bash
export OPENAI_API_KEY="your-openai-api-key"
```

## Optional Email Summary

```bash
export EMAIL_FROM="your.email@gmail.com"
export EMAIL_TO="your.email@gmail.com"
export EMAIL_APP_PASSWORD="your-gmail-app-password"
```

## Security

Never commit these files:

- `client_secret.json`
- `youtube_token.pickle`
- `.env`
- `uploads.csv`
- `upload_log.csv`
- your real videos or thumbnails

The `.gitignore` file already excludes them.
