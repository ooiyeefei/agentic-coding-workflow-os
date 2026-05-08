from __future__ import annotations

import hashlib
import re
import unicodedata

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    """Convert *title* to a kebab-case, ASCII-safe slug for ADR filenames."""
    text = unicodedata.normalize("NFKD", title)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = _NON_ALNUM_RE.sub("-", text)
    slug = text.strip("-")
    if not slug:
        digest = hashlib.sha256(title.encode("utf-8")).hexdigest()[:8]
        slug = f"adr-{digest}"
    return slug


__all__ = ["slugify"]
