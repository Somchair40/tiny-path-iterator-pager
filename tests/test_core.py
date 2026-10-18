import os
import shutil
import tempfile
import unittest

from tiny_path_iterator_pager import PathIteratorPager, Page, PageError


class _TempDir:
    """Context object exposing ``.path``."""

    def __init__(self) -> None:
        self.path = tempfile.mkdtemp(prefix="tiny_path_iterator_pager_")
        self._created: list[str] = []

    def create_files(self, names: list[str]) -> None:
        for name in names:
            full = os.path.join(self.path, name)
            with open(full, "w") as f:
                f.write("")
            self._created.append(name)

    def cleanup(self) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


class TestPathIteratorPager(unittest.TestCase):
    def setUp(self) -> None:
        self._td = _TempDir()

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_empty_directory_single_page(self) -> None:
        pager = PathIteratorPager(self._td.path, page_size=5)
        page = pager.next_page()
        self.assertEqual(page.entries, [])
        self.assertFalse(page.has_more)
        self.assertEqual(page.next_skip, 0)

    def test_empty_directory_next_page_after_exhaustion(self) -> None:
        pager = PathIteratorPager(self._td.path, page_size=5)
        pager.next_page()
        with self.assertRaises(PageError):
            pager.next_page()

    def test_exactly_page_size(self) -> None:
        self._td.create_files(["a", "b", "c"])
        pager = PathIteratorPager(self._td.path, page_size=3)
        page = pager.next_page()
        self.assertEqual(len(page.entries), 3)
        self.assertFalse(page.has_more)
        with self.assertRaises(PageError):
            pager.next_page()

    def test_multiple_pages_preserves_order(self) -> None:
        names = [f"file_{i:03d}" for i in range(7)]
        self._td.create_files(names)
        pager = PathIteratorPager(self._td.path, page_size=3)

        page1 = pager.next_page()
        self.assertEqual(len(page1.entries), 3)
        self.assertTrue(page1.has_more)
        self.assertEqual(page1.next_skip, 3)

        page2 = pager.next_page()
        self.assertEqual(len(page2.entries), 3)
        self.assertTrue(page2.has_more)
        self.assertEqual(page2.next_skip, 6)

        page3 = pager.next_page()
        self.assertEqual(len(page3.entries), 1)
        self.assertFalse(page3.has_more)
        self.assertEqual(page3.next_skip, 7)

        with self.assertRaises(PageError):
            pager.next_page()

        seen = page1.entries + page2.entries + page3.entries
        self.assertEqual(seen, names)

    def test_page_size_one(self) -> None:
        self._td.create_files(["x", "y", "z"])
        pager = PathIteratorPager(self._td.path, page_size=1)
        collected: list[str] = []
        pages_seen = 0
        while True:
            page = pager.next_page()
            collected.extend(page.entries)
            pages_seen += 1
            if not page.has_more:
                break
        self.assertEqual(collected, ["x", "y", "z"])
        self.assertEqual(pages_seen, 3)

    def test_iter_protocol(self) -> None:
        names = [f"f{i}" for i in range(5)]
        self._td.create_files(names)
        pager = PathIteratorPager(self._td.path, page_size=2)
        collected = list(pager)
        self.assertEqual(collected, names)

    def test_iter_protocol_empty(self) -> None:
        pager = PathIteratorPager(self._td.path, page_size=10)
        self.assertEqual(list(pager), [])

    def test_positive_skip(self) -> None:
        names = [f"n{i:02d}" for i in range(5)]
        self._td.create_files(names)
        pager = PathIteratorPager(self._td.path, page_size=2, skip=2)
        page = pager.next_page()
        self.assertEqual(page.entries, ["n02", "n03"])
        self.assertTrue(page.has_more)
        self.assertEqual(page.next_skip, 4)

    def test_skip_beyond_total(self) -> None:
        self._td.create_files(["a", "b"])
        pager = PathIteratorPager(self._td.path, page_size=2, skip=5)
        page = pager.next_page()
        self.assertEqual(page.entries, [])
        self.assertFalse(page.has_more)
        self.assertEqual(page.next_skip, 5)
        with self.assertRaises(PageError):
            pager.next_page()

    def test_skip_equals_total(self) -> None:
        self._td.create_files(["a", "b", "c"])
        pager = PathIteratorPager(self._td.path, page_size=2, skip=3)
        page = pager.next_page()
        self.assertEqual(page.entries, [])
        self.assertFalse(page.has_more)

    def test_invalid_page_size(self) -> None:
        with self.assertRaises(ValueError):
            PathIteratorPager(self._td.path, page_size=0)
        with self.assertRaises(ValueError):
            PathIteratorPager(self._td.path, page_size=-1)

    def test_invalid_skip(self) -> None:
        with self.assertRaises(ValueError):
            PathIteratorPager(self._td.path, skip=-1)

    def test_nonexistent_directory(self) -> None:
        missing = os.path.join(self._td.path, "does_not_exist")
        pager = PathIteratorPager(missing, page_size=2)
        with self.assertRaises(FileNotFoundError):
            pager.next_page()

    def test_file_not_directory(self) -> None:
        filepath = os.path.join(self._td.path, "not_a_dir")
        with open(filepath, "w") as f:
            f.write("")
        pager = PathIteratorPager(filepath, page_size=2)
        with self.assertRaises(NotADirectoryError):
            pager.next_page()

    def test_default_page_size(self) -> None:
        names = [f"d{i:04d}" for i in range(1500)]
        self._td.create_files(names)
        pager = PathIteratorPager(self._td.path)
        self.assertEqual(pager.page_size, 1000)
        page1 = pager.next_page()
        self.assertEqual(len(page1.entries), 1000)
        self.assertTrue(page1.has_more)
        page2 = pager.next_page()
        self.assertEqual(len(page2.entries), 500)
        self.assertFalse(page2.has_more)

    def test_page_is_frozen(self) -> None:
        self._td.create_files(["a"])
        pager = PathIteratorPager(self._td.path, page_size=5)
        page = pager.next_page()
        with self.assertRaises(Exception):
            page.entries = ["b"]  # type: ignore[misc]

    def test_properties(self) -> None:
        pager = PathIteratorPager(self._td.path, page_size=42, skip=3)
        self.assertEqual(pager.directory, self._td.path)
        self.assertEqual(pager.page_size, 42)

    def test_large_page_size_covers_all(self) -> None:
        names = [f"l{i}" for i in range(10)]
        self._td.create_files(names)
        pager = PathIteratorPager(self._td.path, page_size=1000)
        page = pager.next_page()
        self.assertEqual(page.entries, names)
        self.assertFalse(page.has_more)
        self.assertEqual(page.next_skip, 10)


if __name__ == "__main__":
    unittest.main()
