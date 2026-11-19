"""Command line for the RAG pipeline.  python -m rag.cli index | retrieve "question" [--k 4]"""
from __future__ import annotations

import argparse
import sys

from rag.chunking import load_chunks
from rag.index import EMBEDDING_MODEL, build_index, index_version
from rag.retrieve import log_retrieval, retrieve


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="rag.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("index", help="load, chunk and index the knowledge base, then list the chunks")
    ask = sub.add_parser("retrieve", help="show the top-k chunks for a question")
    ask.add_argument("question")
    ask.add_argument("--k", type=int, default=4)
    args = parser.parse_args(argv)

    chunks = load_chunks()
    if args.command == "index":
        print(f"chunks={len(chunks)} index_version={index_version(chunks)} embedding_model={EMBEDDING_MODEL}")
        for chunk in chunks:
            print(f"{chunk.chunk_id}  [{chunk.start}-{chunk.end}]  {chunk.source} {chunk.version}")
        return 0

    collection = build_index(chunks)
    found = retrieve(collection, args.question, args.k)
    log_retrieval(args.question, found)
    for rank, item in enumerate(found, start=1):
        print(f"{rank}. {item.chunk_id}  score={item.score}  ({item.source} {item.version})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
