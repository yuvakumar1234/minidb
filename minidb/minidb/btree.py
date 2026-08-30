"""
BPlusTree — the actual indexing structure, backed by real disk pages
via Pager (not an in-memory tree that merely pretends to persist).

Why a B+Tree specifically (not a plain binary search tree or hash
table): it stays balanced under insertion (via node splitting, same
family of idea as a red-black tree, but shaped for disk: wide nodes
mean fewer page reads per lookup), and — critically for a database —
leaf nodes are linked together, so range queries ("all keys between X
and Y") are fast: find the start once, then walk forward through
linked leaves, no re-traversal needed. This is the same fundamental
structure real databases use for indexes.
"""

import bisect
import pickle
from .pager import Pager
from .node import BTreeNode

HEADER_PAGE_ID = 0


class BPlusTree:
    def __init__(self, filename: str, order: int = 4):
        self.pager = Pager(filename)

        if self.pager.num_pages == 0:
            # Brand-new database file: page 0 is reserved for header
            # metadata, page 1 becomes the initial (empty) root leaf.
            self.pager.allocate_page()  # page 0: header
            root = BTreeNode(self.pager.allocate_page(), is_leaf=True)  # page 1
            self.order = order
            self.root_page_id = root.page_id
            self.key_type = None  # set on first insert; see _check_key_type
            self._write_node(root)
            self._write_header()
        else:
            self._read_header()  # sets self.root_page_id, self.order, self.key_type

    def _check_key_type(self, key):
        """
        A B+Tree needs every key to be mutually comparable — mixing,
        say, strings and integers in the same tree will crash deep
        inside a split or range scan with a confusing TypeError,
        rather than a clear error at the point of the actual mistake.
        Real databases solve this by giving each indexed column a
        fixed type; this is the same idea in miniature: the first key
        ever inserted fixes the tree's key type, and later inserts of
        a different type are rejected immediately, with a clear
        message pointing at the actual cause.
        """
        if self.key_type is None:
            self.key_type = type(key)
            self._write_header()
        elif type(key) is not self.key_type:
            raise TypeError(
                f"key {key!r} is of type {type(key).__name__}, but this database's "
                f"keys are all {self.key_type.__name__} (fixed by the first key ever "
                f"inserted). Mixing key types in one B+Tree breaks ordering — use a "
                f"separate database file per key type."
            )

    # ------------------------------------------------------------------
    # Header (metadata) persistence
    # ------------------------------------------------------------------
    def _write_header(self):
        blob = pickle.dumps({
            "root_page_id": self.root_page_id,
            "order": self.order,
            "key_type": self.key_type,
        })
        self.pager.write_page(HEADER_PAGE_ID, blob)

    def _read_header(self):
        blob = self.pager.read_page(HEADER_PAGE_ID)
        data = pickle.loads(blob)
        self.root_page_id = data["root_page_id"]
        self.order = data["order"]
        self.key_type = data.get("key_type")

    # ------------------------------------------------------------------
    # Node I/O
    # ------------------------------------------------------------------
    def _read_node(self, page_id: int) -> BTreeNode:
        return BTreeNode.deserialize(self.pager.read_page(page_id))

    def _write_node(self, node: BTreeNode):
        self.pager.write_page(node.page_id, node.serialize())

    def _allocate_page(self) -> int:
        return self.pager.allocate_page()

    # ------------------------------------------------------------------
    # Insert (with node splitting, propagated up to a new root if needed)
    # ------------------------------------------------------------------
    def insert(self, key, value):
        self._check_key_type(key)
        root = self._read_node(self.root_page_id)
        result = self._insert_recursive(root, key, value)
        if result is not None:
            sep_key, new_right_page_id = result
            new_root = BTreeNode(self._allocate_page(), is_leaf=False)
            new_root.keys = [sep_key]
            new_root.children = [self.root_page_id, new_right_page_id]
            self.root_page_id = new_root.page_id
            self._write_node(new_root)
            self._write_header()

    def _insert_recursive(self, node: BTreeNode, key, value):
        if node.is_leaf:
            idx = bisect.bisect_left(node.keys, key)
            if idx < len(node.keys) and node.keys[idx] == key:
                node.values[idx] = value  # key already exists: overwrite
                self._write_node(node)
                return None

            node.keys.insert(idx, key)
            node.values.insert(idx, value)

            if len(node.keys) <= self.order - 1:
                self._write_node(node)
                return None

            return self._split_leaf(node)

        idx = bisect.bisect_right(node.keys, key)
        child = self._read_node(node.children[idx])
        result = self._insert_recursive(child, key, value)
        if result is None:
            return None

        sep_key, new_child_page_id = result
        node.keys.insert(idx, sep_key)
        node.children.insert(idx + 1, new_child_page_id)

        if len(node.keys) <= self.order - 1:
            self._write_node(node)
            return None

        return self._split_internal(node)

    def _split_leaf(self, node: BTreeNode):
        mid = len(node.keys) // 2
        new_leaf = BTreeNode(self._allocate_page(), is_leaf=True)
        new_leaf.keys = node.keys[mid:]
        new_leaf.values = node.values[mid:]
        new_leaf.next_leaf = node.next_leaf

        node.keys = node.keys[:mid]
        node.values = node.values[:mid]
        node.next_leaf = new_leaf.page_id

        self._write_node(node)
        self._write_node(new_leaf)
        # The first key of the new right leaf is copied up as the
        # separator — copied, not moved, because leaves must keep every
        # actual key (that's what makes the linked-leaf range scan work).
        return (new_leaf.keys[0], new_leaf.page_id)

    def _split_internal(self, node: BTreeNode):
        mid = len(node.keys) // 2
        up_key = node.keys[mid]

        new_internal = BTreeNode(self._allocate_page(), is_leaf=False)
        new_internal.keys = node.keys[mid + 1:]
        new_internal.children = node.children[mid + 1:]

        node.keys = node.keys[:mid]
        node.children = node.children[:mid + 1]

        self._write_node(node)
        self._write_node(new_internal)
        # Unlike a leaf split, the middle key MOVES up (it's not kept in
        # either child) — internal nodes only route, they don't need to
        # retain every key themselves.
        return (up_key, new_internal.page_id)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def search(self, key):
        node = self._read_node(self.root_page_id)
        while not node.is_leaf:
            idx = bisect.bisect_right(node.keys, key)
            node = self._read_node(node.children[idx])
        idx = bisect.bisect_left(node.keys, key)
        if idx < len(node.keys) and node.keys[idx] == key:
            return node.values[idx]
        return None

    # ------------------------------------------------------------------
    # Range query — this is the payoff of linking leaves together.
    # ------------------------------------------------------------------
    def range_query(self, start, end):
        node = self._read_node(self.root_page_id)
        while not node.is_leaf:
            idx = bisect.bisect_right(node.keys, start)
            node = self._read_node(node.children[idx])

        results = []
        while node is not None:
            for k, v in zip(node.keys, node.values):
                if k > end:
                    return results
                if k >= start:
                    results.append((k, v))
            node = self._read_node(node.next_leaf) if node.next_leaf is not None else None
        return results

    # ------------------------------------------------------------------
    # Delete — intentionally simplified. See README "Known limitations".
    # Removes the key from its leaf but does not rebalance the tree
    # (no borrowing from siblings, no merging underfull nodes). Search,
    # insert, and range queries all remain correct after a delete; the
    # only cost is that the tree can become less space-efficient over
    # many deletes, which real databases solve with sibling
    # merge/redistribute logic.
    # ------------------------------------------------------------------
    def delete(self, key) -> bool:
        node = self._read_node(self.root_page_id)
        while not node.is_leaf:
            idx = bisect.bisect_right(node.keys, key)
            node = self._read_node(node.children[idx])

        idx = bisect.bisect_left(node.keys, key)
        if idx < len(node.keys) and node.keys[idx] == key:
            del node.keys[idx]
            del node.values[idx]
            self._write_node(node)
            return True
        return False

    def close(self):
        self.pager.close()
