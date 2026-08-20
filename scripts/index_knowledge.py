#!/usr/bin/env python3
"""Index knowledge/ into Qdrant. Run inside backend container or with PYTHONPATH=backend."""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.knowledge import index_knowledge_to_qdrant, load_knowledge_documents


def main():
    parser = argparse.ArgumentParser(description="Index Rafaela knowledge base")
    parser.add_argument("--recreate", action="store_true", help="Drop and recreate collection")
    args = parser.parse_args()

    docs = load_knowledge_documents(force_reload=True)
    print(f"Loaded {len(docs)} chunks from knowledge/")

    result = index_knowledge_to_qdrant(recreate=args.recreate)
    print(result)

    if result.get("status") in ("skipped", "error", "empty"):
        print("Note: keyword search still works without Qdrant index.")
        sys.exit(0 if result.get("status") != "error" else 1)


if __name__ == "__main__":
    main()
