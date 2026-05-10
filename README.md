# Automatic YouTube Uploader

This folder is reusable. Put videos in `videos`, optional thumbnails in `thumbnails`, then either generate `uploads.csv` interactively or edit it manually.

## First-Time Setup

```bash
cd "/Volumes/DRIVE A/Automatic uploader"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional AI metadata:

```bash
export OPENAI_API_KEY="your-openai-api-key"
```

Optional Gmail completion email:

```bash
export EMAIL_FROM="your.email@gmail.com"
export EMAIL_TO="your.email@gmail.com"
export EMAIL_APP_PASSWORD="your-gmail-app-password"
```

## CSV Format

`uploads.csv` columns:

```csv
filename,title,description,tags,privacy,publish_at,thumbnail,topic
```

- `filename`: required video filename inside `videos`
- `title`: YouTube title
- `description`: YouTube description
- `tags`: use quotes when entering multiple tags, for example `"python,tutorial"`
- `privacy`: `private`, `public`, or `unlisted`
- `publish_at`: optional schedule time, for example `2026-05-20T15:00:00`
- `thumbnail`: optional path, for example `thumbnails/thumb1.jpg`
- `topic`: used for AI title and description if title or description is blank

## Run

Save common defaults once:

```bash
python batch_upload_api.py --setup
```

After putting new videos in `videos`, ask for details one by one and update `uploads.csv`:

```bash
python batch_upload_api.py --add-videos
```

To edit videos that are already listed in `uploads.csv`:

```bash
python batch_upload_api.py --add-videos --edit-existing
```

Preview only:

```bash
python batch_upload_api.py --dry-run
```

Upload normally with the official YouTube Data API uploader:

```bash
python batch_upload_api.py
```

The API uploader needs a Google OAuth desktop credential saved as `client_secret.json` in this folder.

If the credential downloads to your Downloads folder, run:

```bash
python install_client_secret.py
```

Older Selenium uploader, only if you specifically want browser automation:

```bash
python batch_upload.py
```

Force re-upload videos that already succeeded:

```bash
python batch_upload_api.py --force
```

Clean `upload_log.csv` automatically after a run finishes with no failures:

```bash
python batch_upload_api.py --clean-log
```

Or enable this once inside setup:

```bash
python batch_upload_api.py --setup
```

To clean the log immediately:

```bash
python batch_upload_api.py --clean-log-now
```

The first upload may open Chrome so you can log in to YouTube.
