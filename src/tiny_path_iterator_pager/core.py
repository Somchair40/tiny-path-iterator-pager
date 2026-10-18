from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterator, List, Optional


__all__ = ["PathIteratorPager", "Page", "PageError"]


class PageError(Exception):
    """Raised when a page fetch is attempted after the page boundary was closed."""


@dataclass(frozen=True)
class Page:
    """A single page of directory entries.

    We use a frozen dataclass so callers cannot mutate a page after it has been
    consumed; mutation would desynchronise the pager's skip count and lead to
    skipped or duplicate entries on the next fetch.
    """
    entries: List[str]
    has_more: bool
    next_skip: int


class PathIteratorPager:
    """Iterate over a directory's entries in fixed-size pages.

    The pager holds no open directory handle between fetches. Instead, each
    fetch calls ``os.listdir`` fresh and skips ``next_skip`` entries. This
    costs O(next_skip) per page, which is linear overall, but it keeps memory
    bounded to ``page_size`` entries at a time and is robust against callers
    who pause between fetches — there is no system handle to leak.

    Stable ordering assumption: ``os.listdir`` is deterministic across calls
    for a given directory state on a given platform. If entries are added or
    removed between fetches, the skip offset may land on a different entry,
    which is the accepted trade-off for not holding a handle.
    """

    def __init__(
        self,
        directory: str,
        *,
        page_size: int = 1000,
        skip: int = 0,
    ) -> None:
        if page_size < 1:
            raise ValueError(f"page_size must be >= 1, got {page_size}")
        if skip < 0:
            raise ValueError(f"skip must be >= 0, got {skip}")
        self._directory = directory
        self._page_size = page_size
        self._next_skip = skip
        self._exhausted = False

    @property
    def directory(self) -> str:
        return self._directory

    @property
    def page_size(self) -> int:
        return self._page_size

    def next_page(self) -> Page:
        """Fetch the next page of directory entries.

        Raises ``FileNotFoundError`` if the directory does not exist (propagated
        from ``os.listdir``). Raises ``NotADirectoryError`` if the path is not a
        directory. Raises ``PageError`` if called after the final page was
        already returned.
        """
        if self._exhausted:
            raise PageError("pager is exhausted")

        all_entries: List[str] = sorted(os.listdir(self._directory))

        if self._next_skip >= len(all_entries):
            self._exhausted = True
            return Page(entries=[], has_more=False, next_skip=self._next_skip)

        page_entries = all_entries[self._next_skip : self._next_skip + self._page_size]
        self._next_skip += len(page_entries)
        has_more = self._next_skip < len(all_entries)
        if not has_more:
            self._exhausted = True
        return Page(
            entries=page_entries,
            has_more=has_more,
            next_skip=self._next_skip,
        )

    def __iter__(self) -> Iterator[str]:
        while True:
            page = self.next_page()
            for entry in page.entries:
                yield entry
            if not page.has_more:
                break
