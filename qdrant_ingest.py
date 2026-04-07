"""
Qdrant Ingestion — Energy Co-pilot RAG Pipeline
================================================
Loads rag_documents.json into Qdrant with:
  - Smart chunking   (section-aware, ~400 token target)
  - Dense embeddings (sentence-transformers or OpenAI)
  - Rich metadata    (asset_type, category, section, source doc)
  - Idempotent       (safe to re-run; upserts by chunk ID)

Run:
    python qdrant_ingest.py                 # uses sentence-transformers (local)
    python qdrant_ingest.py --backend openai  # uses text-embedding-3-small

Collection: energy_docs
Vector size: 384  (MiniLM-L6-v2)  |  1536 (OpenAI text-embedding-3-small)

Typical RAG query (example, not run here):
    results = client.search(
        collection_name="energy_docs",
        query_vector=embed("What causes turbine bearing failure?"),
        query_filter=Filter(must=[FieldCondition(key="asset_type",
                                  match=MatchValue(value="turbine"))]),
        limit=5,
    )
"""

import os
import sys
import json
import time
import uuid
import argparse
import re
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue,
    PayloadSchemaType,
)

load_dotenv(Path(__file__).parent / ".env.example")

# ─── Config ───────────────────────────────────────────────────────────────────

COLLECTION     = "energy_docs"
CHUNK_SIZE     = 400    # target tokens per chunk (~1 token ≈ 4 chars)
CHUNK_OVERLAP  = 80     # overlap to preserve context across chunk boundaries
BATCH_SIZE     = 32     # points per Qdrant upsert batch

# ─── Embedding backends ───────────────────────────────────────────────────────

def get_embedder(backend: str):
    """
    Returns (embed_fn, vector_size).
    embed_fn(texts: list[str]) -> list[list[float]]
    """
    if backend == "sentence-transformers":
        from sentence_transformers import SentenceTransformer
        model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        print(f"  Loading model: {model_name} ...")
        model = SentenceTransformer(model_name)
        dim = model.get_sentence_embedding_dimension()

        def embed(texts):
            return model.encode(texts, show_progress_bar=False).tolist()

        return embed, dim

    elif backend == "openai":
        import openai
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in .env.example")
        client = openai.OpenAI(api_key=api_key)
        model_name = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        dim = 1536

        def embed(texts):
            resp = client.embeddings.create(input=texts, model=model_name)
            return [e.embedding for e in resp.data]

        return embed, dim

    else:
        raise ValueError(f"Unknown embedding backend: {backend!r}. Use 'sentence-transformers' or 'openai'")


# ─── Chunker ─────────────────────────────────────────────────────────────────

def chunk_document(doc: dict) -> list[dict]:
    """
    Splits a document into overlapping chunks.
    Preserves section boundaries (ALL-CAPS headings) as natural split points.
    Each chunk carries the full payload for rich filtering in Qdrant.
    """
    text   = doc["content"].strip()
    title  = doc["title"]
    lines  = text.split("\n")

    # Group lines into sections by ALL-CAPS headings
    sections: list[tuple[str, str]] = []   # (section_title, section_body)
    current_heading = "PREAMBLE"
    current_lines   = []

    heading_re = re.compile(r"^[A-Z][A-Z\s\/\-]{4,}$")

    for line in lines:
        stripped = line.strip()
        if heading_re.match(stripped) and len(stripped) > 4:
            if current_lines:
                sections.append((current_heading, "\n".join(current_lines).strip()))
            current_heading = stripped
            current_lines   = []
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_heading, "\n".join(current_lines).strip()))

    # Convert sections → fixed-size chunks with overlap
    chunks = []
    words_all: list[tuple[str, str]] = []  # (word, section_title)

    for sec_title, sec_body in sections:
        for word in sec_body.split():
            words_all.append((word, sec_title))

    target_words = CHUNK_SIZE * 4 // 5   # rough: 1 token ≈ 1.25 words
    overlap_words = CHUNK_OVERLAP * 4 // 5

    i = 0
    chunk_idx = 0
    while i < len(words_all):
        window = words_all[i: i + target_words]
        text_chunk  = " ".join(w for w, _ in window)
        section     = window[0][1] if window else "PREAMBLE"

        chunk_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc['doc_id']}::{chunk_idx}"))

        chunks.append({
            "id":        chunk_id,
            "text":      f"{title}\n\n{section}\n\n{text_chunk}",
            "payload": {
                "doc_id":     doc["doc_id"],
                "title":      title,
                "category":   doc["category"],
                "asset_type": doc["asset_type"],
                "tags":       doc.get("tags", []),
                "section":    section,
                "chunk_idx":  chunk_idx,
                "char_count": len(text_chunk),
            },
        })

        chunk_idx += 1
        i += target_words - overlap_words
        if i >= len(words_all):
            break

    return chunks


# ─── Collection setup ─────────────────────────────────────────────────────────

def setup_collection(client: QdrantClient, dim: int):
    existing = [c.name for c in client.get_collections().collections]

    if COLLECTION in existing:
        info = client.get_collection(COLLECTION)
        existing_dim = info.config.params.vectors.size
        if existing_dim != dim:
            print(f"  Collection exists but vector size mismatch "
                  f"({existing_dim} vs {dim}). Recreating ...")
            client.delete_collection(COLLECTION)
        else:
            print(f"  Collection '{COLLECTION}' already exists (dim={dim}). Upserting.")
            return

    print(f"  Creating collection '{COLLECTION}' (dim={dim}, cosine distance) ...")
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )

    # Payload indexes for fast filtered search
    for field, schema in [
        ("asset_type", PayloadSchemaType.KEYWORD),
        ("category",   PayloadSchemaType.KEYWORD),
        ("section",    PayloadSchemaType.KEYWORD),
        ("tags",       PayloadSchemaType.KEYWORD),
    ]:
        client.create_payload_index(
            collection_name=COLLECTION,
            field_name=field,
            field_schema=schema,
        )
    print("  Payload indexes created.")


# ─── Ingestion ────────────────────────────────────────────────────────────────

def ingest(client: QdrantClient, chunks: list[dict], embed_fn) -> int:
    """Batch-embed and upsert all chunks. Returns total points upserted."""
    total = 0
    for i in tqdm(range(0, len(chunks), BATCH_SIZE), desc="  upserting", unit="batch"):
        batch   = chunks[i: i + BATCH_SIZE]
        texts   = [c["text"] for c in batch]
        vectors = embed_fn(texts)

        points = [
            PointStruct(id=c["id"], vector=v, payload=c["payload"])
            for c, v in zip(batch, vectors)
        ]
        client.upsert(collection_name=COLLECTION, points=points)
        total += len(points)

    return total


# ─── Smoke-test query ─────────────────────────────────────────────────────────

TEST_QUERIES = [
    ("What causes turbine bearing failure?",     "turbine"),
    ("How do I detect compressor valve wear?",   "compressor"),
    ("What are the steps for emergency shutdown?", None),
]


def run_smoke_test(client: QdrantClient, embed_fn):
    print("\n── Smoke-test queries ────────────────────────────────────")
    for query_text, asset_filter in TEST_QUERIES:
        qvec = embed_fn([query_text])[0]
        flt  = (
            Filter(must=[FieldCondition(key="asset_type",
                                        match=MatchValue(value=asset_filter))])
            if asset_filter else None
        )
        hits = client.query_points(
            collection_name=COLLECTION,
            query=qvec,
            query_filter=flt,
            limit=2,
            with_payload=True,
        )
        print(f"\n  Query: \"{query_text}\"")
        if asset_filter:
            print(f"  Filter: asset_type = {asset_filter}")
        for h in hits:
            _, h = h
            print(f"    score={h[0].score:.3f} | [{h[0].payload['category']}] {h[0].payload['title'][:55]}")
            print(f"    section: {h[0].payload['section'][:60]}")


# ─── Entrypoint ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ingest RAG docs into Qdrant")
    parser.add_argument("--backend", default=os.getenv("EMBEDDING_BACKEND",
                                                        "sentence-transformers"),
                        choices=["sentence-transformers", "openai"])
    parser.add_argument("--no-smoke-test", action="store_true")
    args = parser.parse_args()

    data_dir  = Path(os.getenv("DATA_DIR", "./data"))
    json_path = data_dir / "rag_documents.json"

    if not json_path.exists():
        print(f"ERROR: {json_path} not found. Run rag_generator.py first.")
        sys.exit(1)

    # ── Connect to Qdrant ────────────────────────────────────────────────────
    host    = os.getenv("QDRANT_HOST", "localhost")
    port    = int(os.getenv("QDRANT_PORT", 6333))
    api_key = os.getenv("QDRANT_API_KEY") or None

    print(f"Connecting to Qdrant @ {host}:{port} ...")
    try:
        client = QdrantClient(host=host, port=port, api_key=api_key, timeout=10)
        client.get_collections()  # ping
        print("  ✓ Connected.")
    except Exception as e:
        print(f"\nERROR: Cannot reach Qdrant: {e}")
        print("Make sure Docker is running:  docker compose up -d qdrant")
        sys.exit(1)

    # ── Load embedder ────────────────────────────────────────────────────────
    print(f"\nLoading embedder (backend={args.backend}) ...")
    embed_fn, dim = get_embedder(args.backend)
    print(f"  ✓ Vector dimension: {dim}")

    # ── Setup collection ─────────────────────────────────────────────────────
    print(f"\nSetting up Qdrant collection ...")
    setup_collection(client, dim)

    # ── Load + chunk documents ───────────────────────────────────────────────
    print(f"\nLoading documents from {json_path.name} ...")
    with open(json_path) as f:
        docs = json.load(f)
    print(f"  {len(docs)} documents loaded.")

    all_chunks = []
    for doc in docs:
        chunks = chunk_document(doc)
        all_chunks.extend(chunks)

    print(f"  {len(all_chunks)} chunks created "
          f"(avg {len(all_chunks)/len(docs):.1f} per doc).")

    chunk_sizes = [len(c["text"].split()) for c in all_chunks]
    print(f"  Chunk size: min={min(chunk_sizes)} / avg={sum(chunk_sizes)//len(chunk_sizes)} / max={max(chunk_sizes)} words")

    # ── Embed + upsert ───────────────────────────────────────────────────────
    print(f"\nEmbedding and upserting (batch={BATCH_SIZE}) ...")
    t0    = time.time()
    total = ingest(client, all_chunks, embed_fn)
    elapsed = time.time() - t0

    print(f"  ✓ {total} points upserted in {elapsed:.1f}s "
          f"({total/elapsed:.0f} pts/s)")

    # ── Collection info ──────────────────────────────────────────────────────
    info = client.get_collection(COLLECTION)
    print(f"\n── Collection info ───────────────────────────────────────")
    print(f"  Name:         {COLLECTION}")
    print(f"  Points:       {info.points_count}")
    print(f"  Vector size:  {info.config.params.vectors.size}")
    print(f"  Distance:     {info.config.params.vectors.distance}")

    # Category breakdown
    for cat in ["incident_report", "technical_bulletin", "root_cause_analysis", "procedure"]:
        count = client.count(
            collection_name=COLLECTION,
            count_filter=Filter(must=[
                FieldCondition(key="category", match=MatchValue(value=cat))
            ]),
        ).count
        if count:
            print(f"  [{cat:25s}]: {count} chunks")

    # ── Smoke-test ───────────────────────────────────────────────────────────
    if not args.no_smoke_test:
        run_smoke_test(client, embed_fn)

    print("\nDone. Qdrant is ready for RAG queries.")


if __name__ == "__main__":
    main()
