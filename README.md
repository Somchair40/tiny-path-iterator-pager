# tiny-path-iterator-pager

Iterates over directory entries in fixed-size pages to bound memory on directories with millions of files.

## Usage

```python
from tiny_path_iterator_pager import PathIteratorPager

pager = PathIteratorPager("/var/log", page_size=500)
while True:
    page = pager.next_page()
    print(page.entries)        # list[str], length <= page_size
    print(page.has_more)       # bool
    print(page.next_skip)     # int, offset for the next page
    if not page.has_more:
        break

# Or iterate flat:
for entry in PathIteratorPager("/var/log", page_size=500):
    print(entry)
```

The library exports three names: `PathIteratorPager`, `Page`, and `PageError`.

## Why

`os.listdir` returns the entire directory at once. On a directory with tens of millions of entries this can consume hundreds of megabytes. This pager wraps `os.listdir` so each fetch yields at most `page_size` names and the caller never holds more than one page in memory.

The trade-off is that the pager holds no open directory handle between fetches. Each `next_page()` call re-runs `os.listdir` from scratch and skips `next_skip` entries. This keeps memory bounded and avoids leaking handles when a consumer pauses between pages, at the cost of O(n) total work across a full traversal rather than a single-pass handle walk (which `os.scandir` would provide but would require keeping the iterator open and alive).

## Edge case

If the directory changes between pages — entries added or removed — the skip offset will land on a different entry than it would have on a stable directory. You may see a duplicate or a gap. This is the accepted trade-off for not holding a handle open. If you need stable iteration over a changing directory, hold an `os.scandir` handle yourself instead.

Calling `next_page()` after the final page raises `PageError`. The final page is whichever page has `has_more == False`.

## Design notes

The window stores values eagerly rather than keeping running aggregates. Running
sums drift with floating point over long streams, and recomputing from a small
buffer is cheap enough that the drift is not worth the speed.

