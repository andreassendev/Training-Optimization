"""Obsidian Local REST API client for syncing notes to vault.

Uses the obsidian-local-rest-api plugin running on localhost.
The API key is read from OBSIDIAN_API_KEY env var (preferred) or passed in.
"""

from __future__ import annotations

import os
import ssl
from dataclasses import dataclass
from urllib import request
from urllib.parse import quote


@dataclass
class ObsidianClient:
    """Minimal client for Obsidian Local REST API (HTTPS, self-signed cert)."""

    api_key: str
    host: str = "127.0.0.1"
    port: int = 27124

    @classmethod
    def from_env(cls) -> "ObsidianClient":
        api_key = os.environ.get("OBSIDIAN_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OBSIDIAN_API_KEY env var not set. "
                "Find it in your vault's .obsidian/plugins/obsidian-local-rest-api/data.json"
            )
        return cls(api_key=api_key)

    @property
    def base_url(self) -> str:
        return f"https://{self.host}:{self.port}"

    def _ctx(self) -> ssl.SSLContext:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def list_files(self, folder: str = "") -> list[str]:
        """List files at the given folder path (empty string = vault root)."""
        url = f"{self.base_url}/vault/{quote(folder)}"
        if folder and not folder.endswith("/"):
            url += "/"
        req = request.Request(url, headers={"Authorization": f"Bearer {self.api_key}"})
        with request.urlopen(req, context=self._ctx()) as resp:
            import json

            data = json.load(resp)
            return data.get("files", [])

    def read_note(self, path: str) -> str:
        """Read a markdown note from the vault."""
        url = f"{self.base_url}/vault/{quote(path)}"
        req = request.Request(url, headers={"Authorization": f"Bearer {self.api_key}"})
        with request.urlopen(req, context=self._ctx()) as resp:
            return resp.read().decode("utf-8")

    def write_note(self, path: str, content: str) -> None:
        """Create or overwrite a markdown note in the vault.

        Path is relative to vault root, e.g. 'Trening/Plan.md'.
        Folders are created automatically.
        """
        url = f"{self.base_url}/vault/{quote(path)}"
        req = request.Request(
            url,
            data=content.encode("utf-8"),
            method="PUT",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "text/markdown",
            },
        )
        with request.urlopen(req, context=self._ctx()) as resp:
            if resp.status not in (200, 201, 204):
                raise RuntimeError(f"Failed to write {path}: {resp.status}")

    def append_to_note(self, path: str, content: str) -> None:
        """Append content to an existing note (or create if it doesn't exist)."""
        url = f"{self.base_url}/vault/{quote(path)}"
        req = request.Request(
            url,
            data=content.encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "text/markdown",
            },
        )
        with request.urlopen(req, context=self._ctx()) as resp:
            if resp.status not in (200, 201, 204):
                raise RuntimeError(f"Failed to append to {path}: {resp.status}")
