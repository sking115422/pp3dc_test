# PP3DC Local App

This is a local Flask app that rotates through images on localhost:8080 using a folder path from `config.json`.

## Configure

Edit `config.json`:

```json
{
  "folder_path": "/absolute/path/to/images",
  "delay_seconds": 3
}
```

Changes are picked up automatically. The delay can also be adjusted in the web UI.

## Run

1. Create a virtualenv and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Start the server:

```bash
python app.py
```

3. Open the viewer:

- http://127.0.0.1:8080/

## Notes

- The viewer includes Start/Stop and delay controls alongside the slideshow.
- The viewer updates its URL with the current image name for tracking.
