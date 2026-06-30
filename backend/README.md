# ParasFlix Backend

A production-quality, file-based personal media server built with FastAPI. Designed for macOS with Apple VideoToolbox hardware encoding, optimized for serving over ngrok with low upload bandwidth.

## Features

- **HLS Adaptive Streaming** — 1080p, 720p, 480p, 360p with Apple VideoToolbox hardware encoding
- **Lazy Transcoding** — HLS segments generated on first play, then cached
- **Smart Scanning** — Incremental async scanner with modification detection
- **TMDB Integration** — Automatic metadata and artwork fetching (with FFmpeg fallback)
- **File-Based** — No database required; JSON cache + binary assets
- **ngrok Optimized** — 4-second segments, permissive CORS, streaming headers

## Quick Start

```bash
# 1. Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up media directory
mkdir -p ../media/originals/{Movies,"TV Shows",Anime}
mkdir -p ../media/cache/{hls,posters,banners,thumbnails,metadata}
mkdir -p ../logs

# 4. Configure (optional)
# Edit .env to set TMDB_API_KEY and customize paths

# 5. Run
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Media Structure

```
media/originals/
├── Movies/
│   └── Movie Name (2024).mkv
├── TV Shows/
│   └── Breaking Bad/
│       └── Season 01/
│           └── S01E01.mkv
└── Anime/
    └── Naruto/
        └── Season 01/
            └── EP01.mkv
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/library` | Full library listing |
| GET | `/api/v1/search?q=term` | Search media |
| GET | `/api/v1/movie/{id}` | Media detail |
| GET | `/api/v1/poster/{id}` | Poster image |
| GET | `/api/v1/banner/{id}` | Banner image |
| GET | `/api/v1/stream/{id}/master.m3u8` | HLS master playlist |
| GET | `/api/v1/stream/{id}/{quality}/{segment}` | HLS segment |

## Configuration

All configuration via environment variables (`.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `DEBUG` | `false` | Debug mode |
| `MEDIA_ROOT` | `../media/originals` | Path to media files |
| `CACHE_ROOT` | `../media/cache` | Path to cache directory |
| `LOG_DIR` | `../logs` | Path to log files |
| `TMDB_API_KEY` | _(empty)_ | TMDB API key for metadata |
| `HLS_SEGMENT_DURATION` | `4` | HLS segment length in seconds |
| `HLS_MAX_CONCURRENT_TRANSCODES` | `2` | Max simultaneous FFmpeg jobs |
| `SCAN_ON_STARTUP` | `true` | Scan media on server start |
| `SCAN_INTERVAL_SECONDS` | `300` | Background scan interval |

## Requirements

- Python 3.12+
- FFmpeg with VideoToolbox support (macOS)
- FFprobe
