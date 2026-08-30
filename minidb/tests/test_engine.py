"""
Automated tests for minidb. Run: python tests/test_engine.py
"""
import os
import sys
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from minidb import BPlusTree, Engine

PASS = 0
FAIL = 0


def check(desc, expected, actual):
    global PASS, FAIL
    if expected == actual:
        print(f"PASS — {desc}")
        PASS += 1
    else:
        print(f"FAIL — {desc}\n   expected: {expected!r}\n   actual:   {actual!r}")
        FAIL += 1


TEST_DB = "/tmp/minidb_test.db"


def cleanup():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


# --- Test 1: basic insert + search ---
cleanup()
tree = BPlusTree(TEST_DB, order=4)
tree.insert(5, "five")
tree.insert(3, "three")
tree.insert(8, "eight")
check("search finds inserted key", "five", tree.search(5))
check("search finds another inserted key", "eight", tree.search(8))
check("search returns None for missing key", None, tree.search(100))
tree.close()

# --- Test 2: enough inserts to force multiple splits ---
cleanup()
tree = BPlusTree(TEST_DB, order=4)
n = 200
keys = list(range(n))
random.seed(42)
random.shuffle(keys)
for k in keys:
    tree.insert(k, f"value-{k}")

all_found = all(tree.search(k) == f"value-{k}" for k in range(n))
check(f"all {n} keys correctly searchable after many splits", True, all_found)
tree.close()

# --- Test 3: persistence — close and reopen, data must survive ---
tree2 = BPlusTree(TEST_DB, order=4)  # reopen the same file
still_there = all(tree2.search(k) == f"value-{k}" for k in range(n))
check("data survives close + reopen (real disk persistence)", True, still_there)
tree2.close()

# --- Test 4: overwrite an existing key ---
cleanup()
tree = BPlusTree(TEST_DB, order=4)
tree.insert(1, "original")
tree.insert(1, "overwritten")
check("inserting an existing key overwrites its value", "overwritten", tree.search(1))
tree.close()

# --- Test 5: range query ---
cleanup()
tree = BPlusTree(TEST_DB, order=4)
for k in range(1, 21):
    tree.insert(k, k * 10)
results = tree.range_query(5, 10)
expected = [(k, k * 10) for k in range(5, 11)]
check("range query returns correct sorted subset", expected, results)
tree.close()

# --- Test 6: range query across a leaf split boundary ---
# with order=4, a leaf holds at most 3 keys before splitting, so 20
# keys guarantees multiple leaves — this specifically tests that the
# leaf-to-leaf linked list actually works across that boundary.
cleanup()
tree = BPlusTree(TEST_DB, order=4)
for k in range(0, 50, 2):  # even numbers 0..48
    tree.insert(k, k)
results = tree.range_query(10, 30)
expected = [(k, k) for k in range(10, 31, 2)]
check("range query correctly spans multiple leaves", expected, results)
tree.close()

# --- Test 7: delete ---
cleanup()
tree = BPlusTree(TEST_DB, order=4)
tree.insert(1, "a")
tree.insert(2, "b")
deleted = tree.delete(1)
check("delete returns True for existing key", True, deleted)
check("deleted key no longer found", None, tree.search(1))
check("other keys unaffected by delete", "b", tree.search(2))
deleted_again = tree.delete(1)
check("deleting a missing key returns False", False, deleted_again)
tree.close()

# --- Test 8: Engine command layer (SET/GET/DEL/RANGE) ---
cleanup()
engine = Engine(TEST_DB, order=4)
check("SET returns OK", "OK", engine.execute("SET 1 hello"))
check("GET returns stored value", "hello", engine.execute("GET 1"))
check("GET on missing key returns (nil)", "(nil)", engine.execute("GET 999"))
engine.execute("SET 2 world")
engine.execute("SET 3 foo")
range_result = engine.execute("RANGE 1 2")
check("RANGE command returns matching entries", "1 -> hello\n2 -> world", range_result)
check("DEL returns OK for existing key", "OK", engine.execute("DEL 1"))
check("GET after DEL returns (nil)", "(nil)", engine.execute("GET 1"))
engine.close()

# --- Test 9: numeric key ordering (not lexicographic) ---
cleanup()
engine = Engine(TEST_DB, order=4)
for k in [9, 10, 2, 1]:
    engine.execute(f"SET {k} val{k}")
result = engine.execute("RANGE 1 10")
expected_lines = "1 -> val1\n2 -> val2\n9 -> val9\n10 -> val10"
check("numeric keys sort numerically, not as strings (9 before 10)", expected_lines, result)
engine.close()

cleanup()

print(f"\n{'='*40}\nResults: {PASS} passed, {FAIL} failed\n{'='*40}")
sys.exit(0 if FAIL == 0 else 1)
