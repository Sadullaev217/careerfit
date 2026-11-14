"""Copies every file in the documents bucket to a folder, or back again. Part of scripts/backup.sh.

Usage, from apps/api, with SUPABASE_URL and SUPABASE_SECRET_KEY in the environment:
    python -m scripts.storage_backup backup <folder>
    python -m scripts.storage_backup restore <folder>

Files keep their bucket paths (<user id>/<file>). Restoring overwrites files with the same path and
leaves others alone. Prints counts only, never file names, which can contain a person's name.
"""

import argparse
import mimetypes
import os
import sys
from pathlib import Path

import httpx

BUCKET = "documents"
PAGE = 1000


def _client() -> httpx.Client:
    key = os.environ["SUPABASE_SECRET_KEY"]
    return httpx.Client(
        base_url=os.environ["SUPABASE_URL"],
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=120,
    )


def _list(client: httpx.Client, prefix: str) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    while True:
        response = client.post(
            f"/storage/v1/object/list/{BUCKET}",
            json={"prefix": prefix, "limit": PAGE, "offset": len(entries)},
        )
        response.raise_for_status()
        page = response.json()
        entries.extend(page)
        if len(page) < PAGE:
            return entries


def file_paths(client: httpx.Client, prefix: str = "") -> list[str]:
    """Every file under prefix. Folders come back from Supabase without an id."""
    paths = []
    for entry in _list(client, prefix):
        path = f"{prefix}/{entry['name']}" if prefix else str(entry["name"])
        if entry.get("id") is None:
            paths.extend(file_paths(client, path))
        else:
            paths.append(path)
    return paths


def backup(folder: Path) -> int:
    with _client() as client:
        paths = file_paths(client)
        for path in paths:
            response = client.get(f"/storage/v1/object/{BUCKET}/{path}")
            response.raise_for_status()
            target = folder / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(response.content)
    return len(paths)


def restore(folder: Path) -> int:
    files = [path for path in folder.rglob("*") if path.is_file()]
    with _client() as client:
        for file in files:
            path = file.relative_to(folder).as_posix()
            content_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
            client.post(
                f"/storage/v1/object/{BUCKET}/{path}",
                content=file.read_bytes(),
                headers={"Content-Type": content_type, "x-upsert": "true"},
            ).raise_for_status()
    return len(files)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["backup", "restore"])
    parser.add_argument("folder", type=Path)
    arguments = parser.parse_args()
    if arguments.action == "backup":
        arguments.folder.mkdir(parents=True, exist_ok=True)
        print(f"Copied {backup(arguments.folder)} files from the {BUCKET} bucket")
    else:
        print(f"Restored {restore(arguments.folder)} files to the {BUCKET} bucket")
    return 0


if __name__ == "__main__":
    sys.exit(main())
