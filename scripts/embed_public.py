"""Build or refresh BGE-M3 vectors for a schema-v2 (public corpora) catalogue.

Vectors are stored next to v1's, but in their own files:

    <DATA>/vectors/public-vectors.npy   (N, 1024) float16, L2-normalised
    <DATA>/vectors/public-ids.npy       (N,) int64, chunks.id

`embeddings` records which model/dim/version produced each row. The default run
is incremental: vectors for chunks that still exist are kept, new chunks are
encoded, orphans are pruned. `--rebuild` encodes everything again.
"""
import argparse
import json
import os
import sys
import uuid

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "sidecar"))

from app import config, schema  # noqa: E402


def load_chunks(db):
    con = schema.connect(db)
    try:
        rows = con.execute(
            "SELECT id, text, lang, document_id FROM chunks"
            " WHERE visibility = 'tutor' ORDER BY id").fetchall()
    finally:
        con.close()
    return [dict(r) for r in rows]


def _load_existing(vectors_path, ids_path):
    if not (os.path.exists(vectors_path) and os.path.exists(ids_path)):
        return {}
    vecs = np.load(vectors_path)
    ids = np.load(ids_path)
    if vecs.ndim != 2 or ids.ndim != 1 or len(ids) != vecs.shape[0]:
        raise ValueError("vector/ids shape mismatch: %s %s vs %s"
                         % (vectors_path, vecs.shape, ids.shape))
    return {int(cid): vecs[k].astype(np.float32) for k, cid in enumerate(ids)}


def _save(vectors_path, ids_path, ids, vecs):
    os.makedirs(os.path.dirname(os.path.abspath(vectors_path)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(ids_path)), exist_ok=True)
    tmp_v = "%s.%s.npy" % (vectors_path, uuid.uuid4().hex)
    tmp_i = "%s.%s.npy" % (ids_path, uuid.uuid4().hex)
    np.save(tmp_v, vecs)
    np.save(tmp_i, ids)
    os.replace(tmp_v, vectors_path)
    os.replace(tmp_i, ids_path)


def _record(con, ids, model_name, dim, version):
    # Rows for chunks that no longer exist would keep the table out of sync.
    con.execute(
        "DELETE FROM embeddings WHERE model = ? AND chunk_id NOT IN"
        " (SELECT id FROM chunks WHERE visibility = 'tutor')", (model_name,))
    con.executemany(
        "INSERT OR REPLACE INTO embeddings(chunk_id, model, dim, version)"
        " VALUES(?,?,?,?)",
        [(int(cid), model_name, int(dim), version) for cid in ids])
    con.commit()


def embed_chunks(db, vectors_path, ids_path, encoder, model_name="bge-m3",
                 version="fp16-normalized", batch_size=32, rebuild=False,
                 limit=None):
    """Encode missing chunks and rewrite the vector files.

    ``encoder`` is anything with a SentenceTransformer-like ``encode`` method;
    tests pass a deterministic fake so no model is loaded.
    """
    if schema.version(db) != "v2":
        raise ValueError("%s is not a v2 catalogue" % db)
    if rebuild and limit:
        raise ValueError("--rebuild cannot be combined with --limit: "
                         "a partial rebuild would drop the other vectors")
    chunks_all = load_chunks(db)
    chunks = chunks_all[:max(1, int(limit))] if limit else chunks_all
    current = {c["id"]: c for c in chunks_all}
    existing = {} if rebuild else _load_existing(vectors_path, ids_path)
    existing = {cid: v for cid, v in existing.items() if cid in current}

    missing = [c for c in chunks if c["id"] not in existing]
    encoded = 0
    if missing:
        texts = [c["text"] for c in missing]
        arr = np.asarray(encoder.encode(
            texts, batch_size=batch_size, normalize_embeddings=True,
            convert_to_numpy=True, show_progress_bar=False), dtype=np.float32)
        if arr.ndim != 2 or arr.shape[0] != len(texts):
            raise ValueError("encoder returned %s for %d chunks"
                             % (arr.shape, len(texts)))
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        arr = arr / np.maximum(norms, 1e-12)
        for cid, vec in zip([c["id"] for c in missing], arr):
            existing[cid] = vec
        encoded = len(missing)

    ids = sorted(existing)
    if not ids:
        raise ValueError("no chunks to embed")
    vecs = np.stack([existing[i] for i in ids]).astype(np.float16)
    _save(vectors_path, ids_path, np.asarray(ids, dtype=np.int64), vecs)

    con = schema.connect(db)
    try:
        _record(con, ids, model_name, vecs.shape[1], version)
    finally:
        con.close()
    return {"chunks": len(ids), "embedded": encoded,
            "reused": len(ids) - encoded, "dim": int(vecs.shape[1]),
            "vectors": vectors_path, "ids": ids_path}


class Encoder:
    """Lazy SentenceTransformer wrapper; imports torch only when used."""

    def __init__(self, model_path, device="auto"):
        import torch
        from sentence_transformers import SentenceTransformer
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.model = SentenceTransformer(model_path, device=device)
        self.model.max_seq_length = 256

    def encode(self, texts, **kwargs):
        kwargs.setdefault("show_progress_bar", False)
        return self.model.encode(texts, **kwargs)


def build_parser():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", default=os.environ.get("SOCRATIC_PUBLIC_DB")
                   or os.path.join(config.DATA, "public.db"))
    p.add_argument("--vectors", default=config.BGE_V2_VECTORS)
    p.add_argument("--ids", default=config.BGE_V2_IDS)
    p.add_argument("--model", default=config.BGE_V2_MODEL)
    p.add_argument("--device", default="auto", choices=("auto", "cpu", "cuda"))
    p.add_argument("--batch", type=int, default=32)
    p.add_argument("--limit", type=int, default=None,
                   help="only the first N chunks (debugging)")
    p.add_argument("--rebuild", action="store_true",
                   help="re-encode every chunk instead of reusing vectors")
    p.add_argument("--dry-run", action="store_true")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    ver = schema.version(args.db)
    if ver != "v2":
        raise SystemExit("%s is not a v2 catalogue (detected %s); "
                         "build one with scripts/ingest_public.py" % (args.db, ver))
    if args.dry_run:
        chunks = load_chunks(args.db)
        existing = _load_existing(args.vectors, args.ids)
        present = [c for c in chunks if c["id"] in existing]
        missing = [c for c in chunks if c["id"] not in existing]
        out = {"db": args.db, "chunks": len(chunks),
               "existing": len(present), "would_embed": len(missing),
               "dry_run": True}
        print(json.dumps(out, ensure_ascii=False))
        return out
    encoder = Encoder(args.model, device=args.device)
    out = embed_chunks(args.db, args.vectors, args.ids, encoder,
                       model_name=config.BGE_V2_MODEL_NAME,
                       version=config.BGE_V2_EMBED_VERSION,
                       batch_size=args.batch, rebuild=args.rebuild,
                       limit=args.limit)
    out["db"] = args.db
    out["model"] = config.BGE_V2_MODEL_NAME
    out["device"] = encoder.device
    print(json.dumps(out, ensure_ascii=False))
    return out


if __name__ == "__main__":
    raise SystemExit(main())
