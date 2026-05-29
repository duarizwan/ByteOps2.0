"""Dropbox MCP Server.

Exposes Dropbox SDK capabilities as MCP tools via FastMCP.
The Dropbox access token is injected via environment variable
by the Dropbox Agent when spawning this server as a stdio subprocess.

Tools (Reading):
  - list_folder        — list contents of a folder
  - get_metadata       — get metadata for a file or folder
  - search_files       — search for files by query string
  - download_file      — download a file (base64-encoded content)
  - list_shared_links  — list shared links for a path

Tools (Writing):
  - upload_file        — upload a file to Dropbox
  - create_folder      — create a new folder
  - delete_path        — delete a file or folder
  - move_path          — move or rename a file or folder
  - copy_path          — copy a file or folder
  - create_shared_link — create a public shared link for a file or folder
"""

from __future__ import annotations

import base64
import os
import sys
from typing import Any

import dropbox
from dropbox.files import WriteMode, SearchOptions
from dropbox.sharing import RequestedVisibility, SharedLinkSettings
from mcp.server.fastmcp import FastMCP


_MAX_INLINE_BYTES = 1 * 1024 * 1024  # 1 MB


class DropboxClient:
    """Thin synchronous wrapper around the Dropbox Python SDK."""

    def __init__(self, access_token: str) -> None:
        self.dbx = dropbox.Dropbox(access_token)

    # ── Reading ───────────────────────────────────────────────────────────────

    def list_folder(self, path: str = "", recursive: bool = False) -> list[dict]:
        """List the contents of a Dropbox folder."""
        try:
            # Dropbox root is empty string, not "/"
            normalized = "" if path in ("", "/") else path
            result = self.dbx.files_list_folder(normalized, recursive=recursive)
            entries = list(result.entries)
            while result.has_more:
                result = self.dbx.files_list_folder_continue(result.cursor)
                entries.extend(result.entries)
            return [_entry_to_dict(e) for e in entries]
        except dropbox.exceptions.ApiError as e:
            raise RuntimeError(f"Dropbox list_folder error: {e}") from e

    def get_metadata(self, path: str) -> dict:
        """Get metadata for a file or folder at the given path."""
        try:
            meta = self.dbx.files_get_metadata(path)
            return _entry_to_dict(meta)
        except dropbox.exceptions.ApiError as e:
            raise RuntimeError(f"Dropbox get_metadata error: {e}") from e

    def search_files(
        self, query: str, path: str = "", max_results: int = 20
    ) -> list[dict]:
        """Search for files and folders matching the query."""
        try:
            options = SearchOptions(
                path=path if path not in ("", "/") else None,
                max_results=max_results,
            )
            result = self.dbx.files_search_v2(query, options=options)
            matches = []
            for m in result.matches:
                metadata = m.metadata
                # SearchMatchV2 wraps the actual metadata in .metadata.metadata
                if hasattr(metadata, "metadata"):
                    metadata = metadata.metadata
                matches.append(_entry_to_dict(metadata))
            return matches
        except dropbox.exceptions.ApiError as e:
            raise RuntimeError(f"Dropbox search_files error: {e}") from e

    def download_file(self, path: str) -> dict:
        """Download a file from Dropbox. Returns base64-encoded content for files <=1 MB."""
        try:
            meta, response = self.dbx.files_download(path)
            content = response.content
            if len(content) > _MAX_INLINE_BYTES:
                return {
                    "path": path,
                    "name": meta.name,
                    "size": len(content),
                    "warning": (
                        "File is larger than 1 MB and cannot be returned inline. "
                        "Consider using a shared link to access the file."
                    ),
                }
            return {
                "path": path,
                "name": meta.name,
                "content": base64.b64encode(content).decode(),
                "size": len(content),
            }
        except dropbox.exceptions.ApiError as e:
            raise RuntimeError(f"Dropbox download_file error: {e}") from e

    def upload_file(
        self, path: str, content_base64: str, overwrite: bool = True
    ) -> dict:
        """Upload a file to Dropbox. Content must be base64-encoded."""
        try:
            data = base64.b64decode(content_base64)
            mode = WriteMode.overwrite if overwrite else WriteMode.add
            meta = self.dbx.files_upload(data, path, mode=mode)
            return _entry_to_dict(meta)
        except dropbox.exceptions.ApiError as e:
            raise RuntimeError(f"Dropbox upload_file error: {e}") from e

    def create_folder(self, path: str) -> dict:
        """Create a new folder at the given path."""
        try:
            result = self.dbx.files_create_folder_v2(path)
            return _entry_to_dict(result.metadata)
        except dropbox.exceptions.ApiError as e:
            raise RuntimeError(f"Dropbox create_folder error: {e}") from e

    def delete_path(self, path: str) -> dict:
        """Delete a file or folder at the given path."""
        try:
            self.dbx.files_delete_v2(path)
            return {"status": "deleted", "path": path}
        except dropbox.exceptions.ApiError as e:
            raise RuntimeError(f"Dropbox delete_path error: {e}") from e

    def move_path(self, from_path: str, to_path: str) -> dict:
        """Move or rename a file or folder."""
        try:
            result = self.dbx.files_move_v2(from_path, to_path)
            return _entry_to_dict(result.metadata)
        except dropbox.exceptions.ApiError as e:
            raise RuntimeError(f"Dropbox move_path error: {e}") from e

    def copy_path(self, from_path: str, to_path: str) -> dict:
        """Copy a file or folder to a new location."""
        try:
            result = self.dbx.files_copy_v2(from_path, to_path)
            return _entry_to_dict(result.metadata)
        except dropbox.exceptions.ApiError as e:
            raise RuntimeError(f"Dropbox copy_path error: {e}") from e

    # ── Sharing ───────────────────────────────────────────────────────────────

    def create_shared_link(
        self, path: str, requested_visibility: str = "public"
    ) -> dict:
        """Create a shared link for a file or folder. Default visibility is public."""
        try:
            visibility = RequestedVisibility.public
            settings = SharedLinkSettings(requested_visibility=visibility)
            link_meta = self.dbx.sharing_create_shared_link_with_settings(
                path, settings=settings
            )
            return {
                "url": link_meta.url,
                "name": link_meta.name,
                "path": getattr(link_meta, "path_lower", path),
            }
        except dropbox.exceptions.ApiError as e:
            raise RuntimeError(f"Dropbox create_shared_link error: {e}") from e

    def list_shared_links(self, path: str | None = None) -> list[dict]:
        """List shared links, optionally filtered to a specific path."""
        try:
            result = self.dbx.sharing_list_shared_links(path=path)
            return [
                {
                    "url": link.url,
                    "name": link.name,
                    "path": getattr(link, "path_lower", ""),
                }
                for link in result.links
            ]
        except dropbox.exceptions.ApiError as e:
            raise RuntimeError(f"Dropbox list_shared_links error: {e}") from e


# ── Helpers ───────────────────────────────────────────────────────────────────

def _entry_to_dict(entry: Any) -> dict:
    """Convert a Dropbox metadata entry to a plain dict."""
    if isinstance(entry, dropbox.files.FileMetadata):
        return {
            "name": entry.name,
            "path_lower": entry.path_lower,
            "type": "file",
            "size": entry.size,
            "modified": str(entry.server_modified) if entry.server_modified else None,
        }
    if isinstance(entry, dropbox.files.FolderMetadata):
        return {
            "name": entry.name,
            "path_lower": entry.path_lower,
            "type": "folder",
            "size": None,
            "modified": None,
        }
    # Fallback for any other metadata type
    return {
        "name": getattr(entry, "name", ""),
        "path_lower": getattr(entry, "path_lower", ""),
        "type": "unknown",
        "size": getattr(entry, "size", None),
        "modified": None,
    }


# ── Server factory ────────────────────────────────────────────────────────────

def create_dropbox_server(access_token: str) -> FastMCP:
    """Create and return a FastMCP instance with all Dropbox tools wired up."""
    server = FastMCP("ByteOps Dropbox Agent")
    client = DropboxClient(access_token=access_token)

    # ── Reading tools ─────────────────────────────────────────────────────────

    @server.tool()
    def list_folder(path: str = "", recursive: bool = False) -> list[dict]:
        """List the contents of a Dropbox folder.
        Args:
          path: folder path starting with / (e.g. '/Documents'). Use '' or '/' for root.
          recursive: if True, list all nested contents (default: False)
        Returns name, path_lower, type (file/folder), size, and modified date for each entry.
        """
        return client.list_folder(path=path, recursive=recursive)

    @server.tool()
    def get_metadata(path: str) -> dict:
        """Get metadata for a file or folder at the given Dropbox path.
        Args:
          path: full path starting with / (e.g. '/Documents/report.pdf')
        Returns name, path_lower, type, size, and modified date.
        """
        return client.get_metadata(path=path)

    @server.tool()
    def search_files(
        query: str, path: str = "", max_results: int = 20
    ) -> list[dict]:
        """Search for files and folders in Dropbox matching the given query.
        Args:
          query: search string (e.g. 'budget 2024')
          path: limit search to this folder path (default: search entire Dropbox)
          max_results: maximum number of results to return (default 20)
        Returns matching entries with name, path, type, and size.
        """
        return client.search_files(query=query, path=path, max_results=max_results)

    @server.tool()
    def download_file(path: str) -> dict:
        """Download a file from Dropbox.
        Args:
          path: full file path starting with / (e.g. '/Documents/report.pdf')
        Returns base64-encoded content and size. Files larger than 1 MB return a
        warning instead of content — use create_shared_link to access large files.
        """
        return client.download_file(path=path)

    @server.tool()
    def list_shared_links(path: str | None = None) -> list[dict]:
        """List shared links in Dropbox, optionally filtered to a specific path.
        Args:
          path: optional file/folder path to filter results (default: list all shared links)
        Returns url, name, and path for each shared link.
        """
        return client.list_shared_links(path=path)

    # ── Writing tools ─────────────────────────────────────────────────────────

    @server.tool()
    def upload_file(
        path: str, content_base64: str, overwrite: bool = True
    ) -> dict:
        """Upload a file to Dropbox.
        Args:
          path: destination path starting with / (e.g. '/Documents/report.pdf')
          content_base64: base64-encoded file content
          overwrite: if True, overwrite existing file; if False, add with auto-renamed suffix (default: True)
        Returns metadata of the uploaded file.
        IMPORTANT: The user must provide the file content as base64-encoded string.
        """
        return client.upload_file(path=path, content_base64=content_base64, overwrite=overwrite)

    @server.tool()
    def create_folder(path: str) -> dict:
        """Create a new folder in Dropbox.
        Args:
          path: folder path starting with / (e.g. '/Projects/NewFolder')
        Returns metadata of the created folder.
        """
        return client.create_folder(path=path)

    @server.tool()
    def delete_path(path: str) -> dict:
        """Delete a file or folder in Dropbox.
        Args:
          path: full path starting with / (e.g. '/Documents/old-file.txt')
        Returns status and path of the deleted item.
        IMPORTANT: This operation is irreversible. Always confirm with the user before calling.
        """
        return client.delete_path(path=path)

    @server.tool()
    def move_path(from_path: str, to_path: str) -> dict:
        """Move or rename a file or folder in Dropbox.
        Args:
          from_path: current path starting with /
          to_path: destination path starting with /
        Returns metadata of the moved item at its new location.
        IMPORTANT: Confirm the move/rename with the user before calling.
        """
        return client.move_path(from_path=from_path, to_path=to_path)

    @server.tool()
    def copy_path(from_path: str, to_path: str) -> dict:
        """Copy a file or folder to a new location in Dropbox.
        Args:
          from_path: source path starting with /
          to_path: destination path starting with /
        Returns metadata of the new copy.
        """
        return client.copy_path(from_path=from_path, to_path=to_path)

    @server.tool()
    def create_shared_link(
        path: str, requested_visibility: str = "public"
    ) -> dict:
        """Create a shared link for a file or folder in Dropbox.
        Args:
          path: full path starting with / (e.g. '/Documents/report.pdf')
          requested_visibility: 'public' (default) — creates a publicly accessible link
        Returns the shared link URL, name, and path.
        WARNING: Public links are accessible to anyone with the URL. Warn the user
        about privacy implications before creating a public link.
        """
        return client.create_shared_link(
            path=path, requested_visibility=requested_visibility
        )

    return server


if __name__ == "__main__":
    token = os.environ.get("DROPBOX_ACCESS_TOKEN", "")
    if not token:
        print(
            "ERROR: DROPBOX_ACCESS_TOKEN env var is required.",
            file=sys.stderr,
            flush=True,
        )
        sys.exit(1)

    server = create_dropbox_server(access_token=token)
    server.run()
