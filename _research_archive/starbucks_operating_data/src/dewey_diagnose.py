"""Diagnose the Dewey API connection without printing the API key.

    python src/dewey_diagnose.py

Reads DEWEY_API_KEY / DEWEY_ADVAN_PATH from the environment (or .dewey_env) and shows
what the /metadata request returns: status code, content type, final URL, first characters.
"""

import os
import re
from pathlib import Path

import requests

env_file = Path(__file__).resolve().parent.parent / ".dewey_env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        k, _, v = line.strip().removeprefix("export ").partition("=")
        os.environ.setdefault(k, v.strip().strip("'\""))

key = os.environ.get("DEWEY_API_KEY", "")
path = os.environ.get("DEWEY_ADVAN_PATH", "").strip()
print(f"key set: {bool(key)} (length {len(key)})")
def mask(v: str) -> str:
    """Never print anything that could be a credential."""
    return re.sub(r"akv\d_[A-Za-z0-9_\-]+", "<API-KEY-LIKE VALUE>", v.replace(key, "<KEY>") if key else v)


if re.match(r"akv\d_", path) or (key and path == key):
    print("PROBLEM: DEWEY_ADVAN_PATH holds an API key (starts with 'akv'), not the dataset URL.")
    print("Put the dataset's 'Connect to API' URL there: https://app.deweydata.io/external-api/v3/products/<id>/files")
    raise SystemExit(1)
print(f"path: {mask(path)!r}")
if not path.startswith("https://"):
    print("path is not a URL; treating it as a product ID")
    path = f"https://app.deweydata.io/external-api/v3/products/{path}/files"
print(f"looks like an API endpoint (/external-api/ ... /files): "
      f"{'/external-api/' in path and path.rstrip('/').endswith('/files')}")
url = path.rstrip("/") + "/metadata"
r = requests.get(url, headers={"X-API-KEY": key, "accept": "application/json"}, timeout=30)
body = re.sub(r"\s+", " ", r.text[:400])
body = mask(body)
print(f"GET {mask(url)}\n-> HTTP {r.status_code} | content-type: {r.headers.get('content-type')} | final URL: {mask(r.url)}")
print(f"body starts: {body}")
