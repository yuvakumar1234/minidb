"""
Interactive REPL for minidb.

Run:
    python cli.py mydata.db
"""

import sys
from minidb import Engine


def main():
    if len(sys.argv) != 2:
        print("Usage: python cli.py <database-file>")
        sys.exit(1)

    filename = sys.argv[1]
    engine = Engine(filename)

    print(f"minidb — connected to '{filename}'. Commands: SET, GET, DEL, RANGE, EXIT")

    while True:
        try:
            line = input("minidb> ")
        except EOFError:
            break

        if not line.strip():
            continue
        if line.strip().upper() == "EXIT":
            break

        print(engine.execute(line))

    engine.close()
    print("Connection closed.")


if __name__ == "__main__":
    main()
