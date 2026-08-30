# minidb

A small database engine built from scratch in Python — a real,
disk-persisted B+Tree index (not an in-memory dict pretending to be a
database), with a tiny SQL-like command layer on top.

## Why this project

Most "database" toy projects are a dictionary with a `save()` method.
This one implements the actual data structure real databases use for
indexing — a B+Tree — with genuine page-based disk storage: data is
organized into fixed-size 4KB pages on disk, read and written
individually, exactly like SQLite or Postgres do at the storage layer.

## Setup (run this on your laptop)

No dependencies beyond the Python standard library.

```bash
python cli.py mydata.db
```

Then try:
```
minidb> SET 1 apple
OK
minidb> SET 2 banana
OK
minidb> GET 1
apple
minidb> RANGE 1 2
1 -> apple
2 -> banana
minidb> DEL 1
OK
minidb> EXIT
```

Close it and reopen the same file (`python cli.py mydata.db` again) —
your data is still there. That's real persistence, not a session-only
in-memory structure.

Run the automated tests:
```bash
python tests/test_engine.py
```

## How it works

1. **Pager** (`pager.py`) — turns a flat file into fixed-size (4096
   byte) pages. Every page can be read or written independently by
   seeking to `page_id * PAGE_SIZE`. This is the actual persistence
   layer: `os.fsync()` is called after every write, so data survives
   even if the process is killed immediately after.

2. **Node** (`node.py`) — one B+Tree node maps to exactly one page.
   Leaf nodes hold real (key, value) pairs plus a pointer to the
   *next* leaf's page id. Internal nodes hold only keys and child
   pointers — they exist purely to route a search to the right leaf.

3. **BPlusTree** (`btree.py`) — the actual algorithm:
   - **Insert**: descends to the correct leaf, inserts in sorted order.
     If the leaf overflows (`order` limit), it splits into two, and
     the split can cascade upward through parent nodes, potentially
     creating a new root — the standard way a B-Tree stays balanced.
   - **Search**: O(log n) descent from root to leaf.
   - **Range query**: find the starting leaf once, then walk forward
     through the leaf-to-leaf linked list — this is *why* B+Trees
     (not plain binary search trees or hash tables) are the standard
     choice for database indexes: range scans don't need to
     re-traverse the tree at all.

4. **Engine** (`engine.py`) — a tiny text command layer (`SET`, `GET`,
   `DEL`, `RANGE`) on top of the raw tree, the same idea as a query
   parser in miniature.

## A real bug found and fixed while building this

Testing this by mixing string keys (`"name"`, `"age"`) and numeric
keys (`5`, `10`) in the same database crashed deep inside the range
query with a confusing `TypeError: '>' not supported between
instances of 'str' and 'int'` — Python can't order a string against a
number, and the B+Tree comparisons didn't check for that.

**The fix**: the tree now fixes its key type on the very first insert
(same idea as a database column having a fixed type) and rejects a
mismatched key immediately, with a clear error message pointing at
the actual problem — instead of crashing confusingly three layers
away from the real mistake. This is a genuinely good thing to bring
up if asked about testing or debugging in an interview.

## Known limitations (stated on purpose, not hidden)

- **Delete does not rebalance the tree.** A key is removed from its
  leaf, but there's no borrowing from sibling nodes or merging
  underfull nodes — the standard simplification when the algorithmic
  focus is insert/search/range-query correctness. Search, insert, and
  range queries remain fully correct after deletes; the only cost is
  the tree can become less space-efficient after many deletions.
- **One key type per database file.** Mixing e.g. strings and integers
  in the same tree is rejected with a clear error (see above) rather
  than silently producing wrong ordering.
- **Node serialization uses `pickle`**, not a hand-rolled binary
  format. This keeps the complexity focused on the B+Tree algorithm
  itself rather than low-level byte packing — a real production
  database would use a fixed binary layout for speed and
  cross-language compatibility, which this project deliberately
  doesn't attempt.
- **No concurrent access support** — single process/single connection
  only, no locking.

## What to be ready to explain in an interview

- Why a B+Tree specifically, not a binary search tree or hash table
  (balanced under insertion + fast range queries via linked leaves).
- The difference between a leaf split (copies the separator key up,
  keeps it in the leaf) and an internal split (moves the separator key
  up, doesn't duplicate it) — and why that distinction exists.
- Why pages are fixed-size (so `page_id * PAGE_SIZE` gives O(1) direct
  disk access, no scanning to find where a page starts).
- The key-type bug above — a good, honest "tell me about a bug you
  found" story.

## Files

```
minidb/
  pager.py   — fixed-size page read/write, real disk persistence
  node.py    — B+Tree node serialization
  btree.py   — insert/split, search, range query, delete
  engine.py  — SET/GET/DEL/RANGE command layer
cli.py       — interactive REPL
tests/
  test_engine.py — 19 automated checks, all passing
```
