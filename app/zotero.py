"""Zotero access.

Primary path: the local HTTP API exposed by a running Zotero 7 desktop app at
http://localhost:23119/api/ (read-only mirror of the Zotero Web API). We pull
items as CSL-JSON, Zotero's native interchange format, which is exactly what the
matcher and the citeproc renderer both want.

The client is deliberately behind a small interface so a future backend
(Zotero Web API + key, or an exported-file import) can be swapped in without
touching the matcher.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

import requests

ZOTERO_BASE = "http://localhost:23119/api"
# Local API uses user id 0 to mean "the local library".
LOCAL_USER = "users/0"
TIMEOUT = 5
PAGE_SIZE = 100


class ZoteroError(RuntimeError):
    pass


class ZoteroClient:
    def __init__(self, base: str = ZOTERO_BASE) -> None:
        self.base = base.rstrip("/")
        self._cache: dict[str, Any] = {}
        self._cache_time: float = 0.0
        self._cache_ttl = 60.0  # seconds

    # -- connectivity ------------------------------------------------------
    def status(self) -> dict[str, Any]:
        """Return {ok, detail, version?}. Never raises."""
        try:
            r = requests.get(f"{self.base}/{LOCAL_USER}/items",
                             params={"limit": 1, "format": "json"},
                             timeout=TIMEOUT)
            if r.status_code == 200:
                return {"ok": True, "detail": "Connected to local Zotero."}
            return {"ok": False,
                    "detail": f"Zotero responded with HTTP {r.status_code}."}
        except requests.exceptions.ConnectionError:
            return {"ok": False,
                    "detail": "Could not reach Zotero on localhost:23119. "
                              "Is the Zotero desktop app running?"}
        except requests.exceptions.RequestException as e:
            return {"ok": False, "detail": f"Zotero request failed: {e}"}

    # -- collections -------------------------------------------------------
    def collections(self) -> list[dict[str, str]]:
        try:
            r = requests.get(f"{self.base}/{LOCAL_USER}/collections",
                             params={"limit": 200, "format": "json"},
                             timeout=TIMEOUT)
            r.raise_for_status()
            return [{"key": c["key"], "name": c["data"]["name"]}
                    for c in r.json()]
        except requests.exceptions.RequestException as e:
            raise ZoteroError(str(e)) from e

    # -- library -----------------------------------------------------------
    def fetch_library(self, collection: Optional[str] = None,
                      force: bool = False) -> list[dict[str, Any]]:
        """Fetch all items as a list of CSL-JSON dicts (cached briefly)."""
        cache_key = collection or "__all__"
        if (not force and cache_key in self._cache
                and time.time() - self._cache_time < self._cache_ttl):
            return self._cache[cache_key]

        if collection:
            url = f"{self.base}/{LOCAL_USER}/collections/{collection}/items"
        else:
            url = f"{self.base}/{LOCAL_USER}/items"

        items: list[dict[str, Any]] = []
        start = 0
        while True:
            try:
                r = requests.get(url, params={"format": "csljson",
                                              "limit": PAGE_SIZE,
                                              "start": start},
                                 timeout=TIMEOUT * 4)
                r.raise_for_status()
            except requests.exceptions.RequestException as e:
                raise ZoteroError(str(e)) from e
            payload = r.json()
            # csljson responses wrap items under "items".
            batch = payload.get("items", payload) if isinstance(payload, dict) else payload
            if not batch:
                break
            items.extend(batch)
            if len(batch) < PAGE_SIZE:
                break
            start += PAGE_SIZE

        self._cache[cache_key] = items
        self._cache_time = time.time()
        return items

    # -- fallback ----------------------------------------------------------
    @staticmethod
    def load_csljson_file(path: str | Path) -> list[dict[str, Any]]:
        """Load a user-exported CSL-JSON file (offline fallback)."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data.get("items", [])
        return data


client = ZoteroClient()
