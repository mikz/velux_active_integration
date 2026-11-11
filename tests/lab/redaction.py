"""Sanitize collected lab evidence before it is exposed as an artifact.

The control directory is deliberately excluded: its secret receipt is input to
the caller, which must delete it before publishing artifacts. Pairing stores
must never be collected; keyed redaction here is an additional defense for logs.
"""

from __future__ import annotations

import copy
import io
import json
import os
import re
import stat
import tempfile
import zipfile
from pathlib import Path

REDACTED = "[REDACTED]"
_PIN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{3}(?!\d)")
_BEARER = re.compile(r"\b(Bearer[ \t]+)[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_JWT = re.compile(
    r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{5,}\."
    r"[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?![A-Za-z0-9_-])"
)
_SECRET_NAMES = (
    r"iOSDeviceLT[SP]K|AccessoryLT[SP]K|LT[SP]K|private_key|"
    r"long_term_secret_key|long_term_private_key|pairing_key|pairing_secret|shared_secret|"
    r"auth_code|access_token|refresh_token|id_token|token|password|password_confirm|"
    r"client_secret|api_key|api_secret"
)
_SECRET_FIELD = re.compile(
    r"(?P<prefix>(?<!\w)(?P<quote>[\"']?)"
    r"(?:" + _SECRET_NAMES + r")"
    r"(?P=quote)[ \t]*[:=][ \t]*)"
    r"(?P<value>\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|\[REDACTED\]|"
    r"<redacted-test-secret>|[^\s,}\]&;\"'<>]+)",
    re.IGNORECASE,
)
_SECRET_NAME = re.compile(r"(?:" + _SECRET_NAMES + r")", re.IGNORECASE)
_QUERY_SECRET = re.compile(
    r"(?P<prefix>(?:[?&;]|&amp;)(?:token|access_token|refresh_token|auth_code|"
    r"code|api_key|signature|sig|password|client_secret)=)"
    r"[^\s\"'<>\\&#;]+",
    re.IGNORECASE,
)
_HOME_PATH = re.compile(
    r"/(?:Users|home)/(?!runner(?:/|\b))[^\s\"'<>:;,\]\)}]+"
    r"|[A-Za-z]:(?:\\\\|\\)Users(?:\\\\|\\)[^\s\"'<>;,\]\)}]+"
)
_BINARY_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".bmp",
    ".avif",
    ".heic",
    ".mp4",
    ".webm",
    ".mov",
    ".mp3",
    ".wav",
    ".ogg",
    ".pdf",
    ".woff",
    ".woff2",
    ".ttf",
    ".sqlite",
    ".db",
    ".pyc",
    ".gz",
    ".bz2",
    ".xz",
}
_BINARY_MAGIC = (
    b"\x89PNG\r\n\x1a\n",
    b"\xff\xd8\xff",
    b"GIF87a",
    b"GIF89a",
    b"RIFF",
    b"%PDF-",
    b"SQLite format 3\x00",
    b"\x7fELF",
    b"\x1f\x8b",
)


def _text_encoding(data: bytes, name: str) -> str | None:
    if Path(name).suffix.lower() in _BINARY_SUFFIXES or data.startswith(_BINARY_MAGIC):
        return None
    if data.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
        return "utf-32"
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    if b"\x00" in data:
        return None
    return "utf-8"


def sanitize_artifacts(root: Path, secrets: list[str], *, check: bool = False) -> None:
    """Redact UTF text files and ZIP text members, preserving binary contents.

    Exact secrets and their JSON-escaped forms, HAP PINs, Bearer credentials,
    JWTs, authentication fields, URL credentials, home paths, and HAP keys are
    removed, including credentials inside JSON-encoded strings. Rewrites are atomic. Symlinks
    are never followed or rewritten. ``root/control`` is never read or changed;
    the caller must remove the control receipt before delivering the artifacts.
    Unreadable files and malformed ZIPs raise instead of claiming sanitization.
    ``check`` rejects any needed redaction without writing files. It also rejects
    symlinks and a nonempty control directory at the publication boundary.
    """
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("artifact root must be a real directory")
    secret_forms = set()
    for secret in secrets:
        if not isinstance(secret, str):
            raise TypeError("artifact secrets must be strings")
        if secret:
            secret_forms.add(secret)
            secret_forms.add(json.dumps(secret, ensure_ascii=True)[1:-1])
            secret_forms.add(json.dumps(secret, ensure_ascii=False)[1:-1])
    exact = (
        re.compile(
            "|".join(re.escape(value) for value in sorted(secret_forms, key=len, reverse=True))
        )
        if secret_forms
        else None
    )

    def redact_plain(text: str) -> str:
        if exact is not None:
            text = exact.sub(REDACTED, text)
        text = _PIN.sub(REDACTED, text)
        text = _BEARER.sub(lambda match: match[1] + REDACTED, text)
        text = _JWT.sub(REDACTED, text)

        def redact_key(match: re.Match[str]) -> str:
            value = match["value"]
            quote = value[0] if value.startswith(('"', "'")) else ""
            return match["prefix"] + quote + REDACTED + quote

        text = _SECRET_FIELD.sub(redact_key, text)
        text = _QUERY_SECRET.sub(lambda match: match["prefix"] + REDACTED, text)
        return _HOME_PATH.sub("[PRIVATE_PATH]", text)

    def redact_json(value, depth: int):
        if depth > 128:
            raise ValueError("artifact JSON nesting exceeds sanitization limit")
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                cleaned_key = redact_plain(key)
                if cleaned_key in result:
                    raise ValueError("Redaction would merge JSON evidence keys")
                result[cleaned_key] = (
                    REDACTED if _SECRET_NAME.fullmatch(key) else redact_json(item, depth + 1)
                )
            return result
        if isinstance(value, list):
            return [redact_json(item, depth + 1) for item in value]
        if isinstance(value, str):
            return redact(value, depth + 1)
        return value

    def redact(text: str, depth: int = 0) -> str:
        if depth > 128:
            raise ValueError("artifact encoded JSON nesting exceeds sanitization limit")
        if text.lstrip().startswith(("{", "[")):
            try:
                value = json.loads(text)
            except ValueError:
                pass
            else:
                cleaned = redact_json(value, depth)
                return text if cleaned == value else json.dumps(cleaned, ensure_ascii=False)
        # Playwright traces are JSONL, including escaped POST bodies and snapshots.
        if "\n" in text:
            result = []
            for line in text.splitlines(keepends=True):
                body = line.rstrip("\r\n")
                result.append(redact(body, depth) + line[len(body) :])
            return "".join(result)
        return redact_plain(text)

    def transform(data: bytes, name: str, depth: int = 0) -> bytes:
        is_zip = Path(name).suffix.lower() == ".zip" or data.startswith(b"PK\x03\x04")
        if is_zip:
            if depth >= 4:
                raise ValueError("artifact ZIP nesting exceeds sanitization limit")
            output = io.BytesIO()
            changed = False
            with (
                zipfile.ZipFile(io.BytesIO(data)) as source,
                zipfile.ZipFile(output, "w") as target,
            ):
                target.comment = transform(source.comment, "archive-comment.txt", depth + 1)
                changed |= target.comment != source.comment
                names = set()
                for original in source.infolist():
                    info = copy.copy(original)
                    info.filename = redact_plain(info.filename)
                    if info.filename in names:
                        raise ValueError("Redaction would merge archive members")
                    names.add(info.filename)
                    info.comment = transform(info.comment, "member-comment.txt", depth + 1)
                    payload = source.read(original)
                    cleaned = transform(payload, original.filename, depth + 1)
                    changed |= (
                        cleaned != payload
                        or info.comment != original.comment
                        or info.filename != original.filename
                    )
                    target.writestr(info, cleaned)
            return output.getvalue() if changed else data
        encoding = _text_encoding(data, name)
        if encoding is None:
            return data
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            return data
        cleaned = redact(text)
        return cleaned.encode(encoding) if cleaned != text else data

    for directory, directories, files in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        if check:
            for name in (*directories, *files):
                path = directory_path / name
                if path.is_symlink():
                    raise ValueError("Symlink is not publishable evidence")
                if path == root / "control" and path.is_dir() and any(path.iterdir()):
                    raise ValueError("Control data is not publishable evidence")
        directories[:] = [
            name
            for name in directories
            if not (directory_path / name).is_symlink()
            and directory_path / name != root / "control"
        ]
        for name in files:
            path = directory_path / name
            if path.is_symlink() or not path.is_file():
                continue
            original = path.read_bytes()
            cleaned = transform(original, name)
            if cleaned == original:
                continue
            if check:
                raise ValueError(
                    "Evidence requires redaction: " + path.relative_to(root).as_posix()
                )
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(
                    dir=path.parent, prefix=".redacting-", delete=False
                ) as out:
                    temporary = Path(out.name)
                    out.write(cleaned)
                temporary.chmod(stat.S_IMODE(path.stat().st_mode))
                os.replace(temporary, path)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
