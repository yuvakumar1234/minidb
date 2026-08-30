"""
Pager — the layer that turns a flat file on disk into a set of
fixed-size "pages" that can be individually read and written.

This is the same fundamental idea real databases (SQLite, Postgres)
use: instead of reading/writing the whole file, you address it in
fixed-size chunks (a "page"), so a tree node maps cleanly onto one
page and can be loaded/saved independently of every other node.
"""

import os

PAGE_SIZE = 4096


class Pager:
    def __init__(self, filename: str):
        self.filename = filename
        file_exists = os.path.exists(filename)
        # 'r+b' requires the file to exist; create it first if it doesn't.
        if not file_exists:
            open(filename, "wb").close()
        self.file = open(filename, "r+b")
        self.file.seek(0, os.SEEK_END)
        self.file_length = self.file.tell()

    @property
    def num_pages(self) -> int:
        return self.file_length // PAGE_SIZE

    def read_page(self, page_id: int) -> bytes:
        offset = page_id * PAGE_SIZE
        if offset >= self.file_length:
            raise IndexError(f"page {page_id} does not exist (file has {self.num_pages} pages)")
        self.file.seek(offset)
        data = self.file.read(PAGE_SIZE)
        return data

    def write_page(self, page_id: int, data: bytes):
        if len(data) > PAGE_SIZE:
            raise ValueError(f"serialized node ({len(data)} bytes) exceeds PAGE_SIZE ({PAGE_SIZE})")
        # Pad to a full page so every page is exactly PAGE_SIZE bytes —
        # this is what lets us seek directly to page_id * PAGE_SIZE
        # instead of scanning the file to find where a page starts.
        padded = data.ljust(PAGE_SIZE, b"\x00")
        offset = page_id * PAGE_SIZE
        self.file.seek(offset)
        self.file.write(padded)
        self.file.flush()
        os.fsync(self.file.fileno())  # force it to actual disk, not just OS buffer
        self.file_length = max(self.file_length, offset + PAGE_SIZE)

    def allocate_page(self) -> int:
        """Reserves a brand-new page at the end of the file and returns its id."""
        new_page_id = self.num_pages
        self.write_page(new_page_id, b"")  # reserve the space, all zero bytes
        return new_page_id

    def close(self):
        self.file.close()
