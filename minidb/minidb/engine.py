"""
Engine — a thin command layer on top of BPlusTree, giving it a tiny
query language instead of only a raw Python API. Not real SQL, but
the same idea in miniature: text in, structured operation out.

Supported commands:
    SET <key> <value>
    GET <key>
    DEL <key>
    RANGE <start> <end>
"""

from .btree import BPlusTree


class Engine:
    def __init__(self, filename: str, order: int = 4):
        self.tree = BPlusTree(filename, order=order)

    def execute(self, command: str) -> str:
        parts = command.strip().split(maxsplit=2)
        if not parts:
            return ""

        op = parts[0].upper()

        if op == "SET":
            if len(parts) != 3:
                return "ERROR: usage SET <key> <value>"
            key = self._coerce(parts[1])
            value = parts[2]
            try:
                self.tree.insert(key, value)
            except TypeError as e:
                return f"ERROR: {e}"
            return "OK"

        if op == "GET":
            if len(parts) != 2:
                return "ERROR: usage GET <key>"
            key = self._coerce(parts[1])
            result = self.tree.search(key)
            return result if result is not None else "(nil)"

        if op == "DEL":
            if len(parts) != 2:
                return "ERROR: usage DEL <key>"
            key = self._coerce(parts[1])
            deleted = self.tree.delete(key)
            return "OK" if deleted else "(nil)"

        if op == "RANGE":
            if len(parts) != 3:
                return "ERROR: usage RANGE <start> <end>"
            start = self._coerce(parts[1])
            end = self._coerce(parts[2])
            results = self.tree.range_query(start, end)
            if not results:
                return "(empty)"
            return "\n".join(f"{k} -> {v}" for k, v in results)

        return f"ERROR: unknown command '{op}'"

    @staticmethod
    def _coerce(token: str):
        """Keys typed as numbers behave as numbers (so ordering/ranges
        work numerically, not lexicographically) — '9' should come
        before '10'."""
        try:
            return int(token)
        except ValueError:
            try:
                return float(token)
            except ValueError:
                return token

    def close(self):
        self.tree.close()
