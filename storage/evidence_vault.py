import hashlib
import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SPACES = re.compile(r"[^\S\n]+")
BLANK_LINES = re.compile(r"\n{3,}")


def normalise_text(text: str) -> str:
    """The one form of page text that is hashed, saved and sent to the model.

    NFC, no control or zero-width characters, runs of spaces collapsed, at most one blank line.
    Applying it twice changes nothing.
    """
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch) not in ("Cc", "Cf"))
    lines = (SPACES.sub(" ", line).strip() for line in text.split("\n"))
    return BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Snapshot:
    sha256: str
    text: str
    url: str
    final_url: str
    status: int
    retrieved_at: datetime
    language: str
    redirect_hops: list[str] = field(default_factory=list)


class EvidenceVault:
    def __init__(self, directory: Path):
        self.directory = Path(directory)

    def save(self, text: str, *, url: str, final_url: str, status: int, language: str,
             redirect_hops: list[str] | None = None, retrieved_at: datetime | None = None) -> Snapshot:
        text = normalise_text(text)
        digest = sha256_of(text)
        retrieved_at = retrieved_at or datetime.now(timezone.utc)
        hops = list(redirect_hops or [])
        self.directory.mkdir(parents=True, exist_ok=True)

        # Same text, same file: a snapshot is written once and never changed.
        if not self._text_path(digest).exists():
            self._write_new(self._text_path(digest), text)
            meta = {
                "url": url,
                "final_url": final_url,
                "status": status,
                "retrieved_at": retrieved_at.isoformat(),
                "sha256": digest,
                "language": language,
                "redirect_hops": hops,
            }
            self._write_new(self._meta_path(digest), json.dumps(meta, ensure_ascii=False, indent=2))
        return Snapshot(digest, text, url, final_url, status, retrieved_at, language, hops)

    def load_text(self, digest: str) -> str:
        text = self._text_path(digest).read_text(encoding="utf-8")
        if sha256_of(text) != digest:
            raise ValueError(f"snapshot {digest[:12]} was changed after it was saved")
        return text

    def load_meta(self, digest: str) -> dict:
        return json.loads(self._meta_path(digest).read_text(encoding="utf-8"))

    def _text_path(self, digest: str) -> Path:
        return self.directory / f"{digest}.txt"

    def _meta_path(self, digest: str) -> Path:
        return self.directory / f"{digest}.json"

    def _write_new(self, path: Path, content: str) -> None:
        temp = path.with_name(path.name + ".tmp")
        with open(temp, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o444)
        os.replace(temp, path)
