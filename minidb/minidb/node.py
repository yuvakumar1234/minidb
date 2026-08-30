"""
BTreeNode — one node of the B+Tree, corresponding to exactly one disk
page.

Two kinds of node:
- Leaf nodes hold the actual (key, value) pairs, plus a pointer to the
  NEXT leaf's page id — this linked-list-of-leaves is what makes range
  queries ("give me everything between key A and key B") fast: once
  you find the starting leaf, you just walk forward, no need to
  re-traverse the tree.
- Internal nodes hold only keys and pointers (page ids) to child
  nodes — they exist purely to route a search down to the right leaf.

Serialization uses `pickle` for the node's Python object, padded to
fit inside one fixed-size page. A hand-rolled byte-level binary format
would be more "authentic" to how production databases work, but would
add a lot of low-level packing/unpacking code without teaching a new
concept — the actual point of this project is the B+Tree algorithm
itself (splitting, routing, range scans), so that's where the
complexity is deliberately spent.
"""

import pickle
from .pager import PAGE_SIZE


class BTreeNode:
    def __init__(self, page_id: int, is_leaf: bool):
        self.page_id = page_id
        self.is_leaf = is_leaf
        self.keys = []
        self.values = []       # only meaningful for leaves — one value per key
        self.children = []     # only meaningful for internal nodes — one more child than keys
        self.next_leaf = None  # only meaningful for leaves — page_id of the next leaf, or None

    def serialize(self) -> bytes:
        data = {
            "page_id": self.page_id,
            "is_leaf": self.is_leaf,
            "keys": self.keys,
            "values": self.values,
            "children": self.children,
            "next_leaf": self.next_leaf,
        }
        blob = pickle.dumps(data)
        if len(blob) > PAGE_SIZE:
            raise ValueError(
                f"node with {len(self.keys)} keys serialized to {len(blob)} bytes, "
                f"exceeding PAGE_SIZE ({PAGE_SIZE}) — lower the tree order or store "
                f"large values out-of-line instead of inline in the node."
            )
        return blob

    @staticmethod
    def deserialize(blob: bytes) -> "BTreeNode":
        # Pages are zero-padded; pickle streams stop at their own natural
        # end marker, so trailing zero bytes are simply ignored.
        data = pickle.loads(blob)
        node = BTreeNode(data["page_id"], data["is_leaf"])
        node.keys = data["keys"]
        node.values = data["values"]
        node.children = data["children"]
        node.next_leaf = data["next_leaf"]
        return node
