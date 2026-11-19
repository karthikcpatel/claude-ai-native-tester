"""Command line for the RAG pipeline.

  python -m rag.cli index
  python -m rag.cli retrieve "question" [--k 4]
  python -m rag.cli ask "question" [--k 4]
  python -m rag.cli check-key
"""
from __future__ import annotations

import argparse
import sys

from rag.chunking import load_chunks
from rag.index import EMBEDDING_MODEL, build_index, index_version
from rag.generate import MissingApiKey, generate, require_api_key
from rag.retrieve import log_answer, log_retrieval, retrieve


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="rag.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("index", help="load, chunk and index the knowledge base, then list the chunks")
    ask = sub.add_parser("retrieve", help="show the top-k chunks for a question")
    ask.add_argument("question")
    ask.add_argument("--k", type=int, default=4)
    reply = sub.add_parser("ask", help="retrieve, then let Claude answer from the chunks or abstain")
    reply.add_argument("question")
    reply.add_argument("--k", type=int, default=4)
    sub.add_parser("check-key", help="say whether ANTHROPIC_API_KEY is available (never prints the key)")
    args = parser.parse_args(argv)

    if args.command == "check-key":
        try:
            key = require_api_key()
        except MissingApiKey as error:
            print(f"key: MISSING ({error})")
            return 1
        print(f"key: present, {len(key)} characters")
        return 0

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
    if args.command == "retrieve":
        return 0

    try:
        answer = generate(args.question, found)
    except MissingApiKey as error:
        print(f"cannot answer: {error}")
        return 1
    log_answer(args.question, found, answer)
    print()
    print(answer.text)
    print()
    print(f"abstained={answer.abstained} model={answer.model} prompt={answer.prompt_version} latency={answer.latency_s}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
