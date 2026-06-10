# AGENTS.md — BookerServer

## Overview
Single-file Flask server that syncs audiobook progress between an Android phone and a Garmin watch.
Source: `books/` subdirectories (`.mp3` / `.m4b`), database: `books/books.json`, no DBMS.

## Commands
```powershell
# Run (debug, port 8080)
python main.py

# Docker
docker build -t booker . && docker run -p 8080:8080 -v "$PWD/books:/app/books" booker
```

No test runner, no lint, no typecheck, no CI.

## Architecture
- **Single entrypoint**: `main.py` (`app = Flask(__name__)`, Werkzeug dev server on `0.0.0.0:8080`).
- **Virtual env**: `venv/` at repo root.

### Book identity
A book = a subdirectory under `books/`. The `crc` (ID) is the MD5 hex digest of the *first* audio file in that directory. The `/update` endpoint scans `books/` for new subdirectories, computes metadata (crc, chapter list, durations via TinyTag), and appends entries to `books/books.json`.

### books/books.json schema
A JSON array of objects like:
```json
{
  "directory": "Book Title",     // subdirectory name under books/
  "crc": "md5hex",               // book ID
  "chapters": ["file1.m4b", ...],// sorted audio filenames
  "chapterDurations": [123, ...],// seconds per chapter
  "duration": 456,               // total seconds
  "position": 0,                 // current playback position within current chapter (seconds)
  "chapter": 0,                  // current chapter index
  "complete": false,
  "type": "m4a",
  "lastWriteDevice": "PHONE",    // "PHONE" or "WATCH"
  "lastWriteTime": 1750446858136,// epoch ms
  "lastReadDevice": "PHONE",
  "lastReadTime": 1750446858136
}
```

### Endpoints (all in `main.py`)
| Route | Method | Purpose |
|---|---|---|
| `/update` | GET | Scan `books/` for new/removed subdirectories; rebuild metadata |
| `/list` | GET/POST | Return all books keyed by `crc` |
| `/book/<id>/<chapter>` | GET | Serve a chapter audio file by book crc and chapter index |
| `/backup` | POST | Accept backup JSON with `data` array; merge `position`/`chapter` into db |
| `/restore` | POST | Accept crc list; return each book's current `position`/`chapter` |
| `/progress` | POST | Sync progress between phone and watch (complex conflict-resolution logic) |
| `/checkin` | POST | Phone writes its current position/chapter to db |

### Non-standard form parser
The `/progress` and `/checkin` endpoints accept a Scala-like form format: `key=>value, key2=>value2`. The `formToJson()` function in `main.py:64` parses this into a Python dict. Do not assume standard JSON or form-encoded input — clients send this custom format.

### Progress sync logic (`/progress`)
The sync algorithm compares `lastWriteDevice`, `lastWriteTime`, `lastReadDevice`, `lastReadTime`, and the calculated absolute position. The device claiming the most recent authoritative write wins. The `DEVICE` field in the request determines whether the caller is `PHONE` or `WATCH`. Phone callers always get server state pushed back to them; watch callers trigger a conflict-resolution decision tree.

## Gotchas
- `calculateId` MD5s the first file. If the first file changes, the book becomes a new identity.
- `books/books.json` is read/written on nearly every request — there is no concurrency control.
- `testJson.py` is a manual helper for tweaking book progress data; it is not a test.
- File paths use forward slashes even on Windows (`os.getcwd()` + `'/'` are hardcoded).
- The `books/` directory is a Docker volume; book data must exist there for the server to work.
