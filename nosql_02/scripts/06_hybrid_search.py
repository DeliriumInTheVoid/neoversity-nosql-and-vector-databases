import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from dotenv import load_dotenv
from pinecone import Pinecone
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer


PROJECT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_DIR / ".env"
DATA_FILE = PROJECT_DIR / "data" / "arxiv_subset.parquet"
MODEL_DIR = PROJECT_DIR / "assets" / "specter2_base"
MODEL_NAME = "allenai/specter2_base"

INDEX_NAME = "arxiv-papers"
DISPLAY_TOP_K = 5
RETRIEVE_TOP_K = 50
RRF_K = 60

QUERIES = [
    "BERT fine-tuning",
    "Yann LeCun convolutional networks",
    "making computers understand human emotions from text",
]


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def get_api_key() -> str:
    load_dotenv(ENV_FILE)
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        raise RuntimeError(f"PINECONE_API_KEY is missing in {ENV_FILE}")
    return api_key


def clean_text(value) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).split())


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:[-_][a-z0-9]+)?", text.lower())


def build_bm25_index(df: pd.DataFrame) -> BM25Okapi:
    documents = (
        df["title"].fillna("").astype(str)
        + " "
        + df["abstract"].fillna("").astype(str)
    )
    tokenized_documents = [tokenize(document) for document in documents]
    return BM25Okapi(tokenized_documents)


def load_model() -> tuple[SentenceTransformer, str]:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    if device == "cuda":
        print(f"CUDA device: {torch.cuda.get_device_name(0)}")

    model_path = MODEL_DIR if MODEL_DIR.exists() else MODEL_NAME
    print(f"Loading model: {model_path}")
    model = SentenceTransformer(str(model_path), device=device)
    return model, device


def encode_query(model: SentenceTransformer, query: str, device: str) -> np.ndarray:
    embedding = model.encode(
        query,
        show_progress_bar=False,
        normalize_embeddings=True,
        convert_to_numpy=True,
        device=device,
    )
    return np.asarray(embedding, dtype=np.float32)


def bm25_search(bm25: BM25Okapi, query: str, top_k: int = RETRIEVE_TOP_K) -> list[dict]:
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    scores = bm25.get_scores(query_tokens)
    top_indices = np.argsort(-scores)[:top_k]
    results = []
    for rank, doc_idx in enumerate(top_indices, start=1):
        results.append(
            {
                "doc_idx": int(doc_idx),
                "rank": rank,
                "score": float(scores[doc_idx]),
            }
        )
    return results


def get_matches(response) -> list:
    matches = getattr(response, "matches", None)
    if matches is not None:
        return list(matches)
    return list(response.get("matches", []))


def get_match_value(match, key: str, default=None):
    if isinstance(match, dict):
        return match.get(key, default)
    return getattr(match, key, default)


def parse_paper_id(match_id: str) -> int | None:
    if not match_id.startswith("paper_"):
        return None
    try:
        return int(match_id.replace("paper_", "", 1))
    except ValueError:
        return None


def vector_search(index, model: SentenceTransformer, query: str, device: str, top_k: int = RETRIEVE_TOP_K) -> list[dict]:
    query_embedding = encode_query(model, query, device)
    response = index.query(
        vector=query_embedding.tolist(),
        top_k=top_k,
        include_metadata=True,
    )

    matches = sorted(
        get_matches(response),
        key=lambda match: get_match_value(match, "score", 0.0),
        reverse=True,
    )

    results = []
    for rank, match in enumerate(matches, start=1):
        match_id = get_match_value(match, "id", "")
        doc_idx = parse_paper_id(match_id)
        if doc_idx is None:
            continue
        results.append(
            {
                "doc_idx": doc_idx,
                "rank": rank,
                "score": float(get_match_value(match, "score", 0.0)),
            }
        )
    return results


def reciprocal_rank_fusion(
    ranked_lists: list[list[dict]],
    rrf_k: int = RRF_K,
    top_k: int = DISPLAY_TOP_K,
) -> list[dict]:
    fused_scores: dict[int, float] = {}
    ranks_by_method: dict[int, dict[str, int | None]] = {}
    method_names = ["bm25", "vector"]

    for method_name, results in zip(method_names, ranked_lists):
        seen_docs = set()
        for item in results:
            doc_idx = item["doc_idx"]
            if doc_idx in seen_docs:
                continue
            seen_docs.add(doc_idx)

            rank = item["rank"]
            fused_scores[doc_idx] = fused_scores.get(doc_idx, 0.0) + 1.0 / (rrf_k + rank)
            ranks_by_method.setdefault(doc_idx, {"bm25": None, "vector": None})
            ranks_by_method[doc_idx][method_name] = rank

    sorted_items = sorted(fused_scores.items(), key=lambda item: item[1], reverse=True)[:top_k]
    return [
        {
            "doc_idx": doc_idx,
            "score": score,
            "rank": rank,
            "bm25_rank": ranks_by_method[doc_idx]["bm25"],
            "vector_rank": ranks_by_method[doc_idx]["vector"],
        }
        for rank, (doc_idx, score) in enumerate(sorted_items, start=1)
    ]


def format_rank(value) -> str:
    return "-" if value is None else str(value)


def print_results(title: str, df: pd.DataFrame, results: list[dict], score_name: str) -> None:
    print(f"\n{title}")
    if not results:
        print("No results found.")
        return

    for item in results[:DISPLAY_TOP_K]:
        row = df.iloc[item["doc_idx"]]
        abstract = clean_text(row["abstract"])
        authors = clean_text(row["authors"])
        score = item["score"]

        if score_name == "RRF":
            score_line = (
                f"RRF={score:.5f} | BM25 rank={format_rank(item['bm25_rank'])} "
                f"| vector rank={format_rank(item['vector_rank'])}"
            )
        else:
            score_line = f"{score_name}={score:.4f}"

        print(f"{item['rank']}. {row['title']}")
        print(f"   {score_line} | category={row['category']} | year={row['year']}")
        print(f"   authors={authors[:180]}")
        print(f"   {abstract[:300]}...")


def compare_methods(bm25_results: list[dict], vector_results: list[dict], hybrid_results: list[dict]) -> None:
    bm25_top = {item["doc_idx"] for item in bm25_results[:DISPLAY_TOP_K]}
    vector_top = {item["doc_idx"] for item in vector_results[:DISPLAY_TOP_K]}
    hybrid_top = {item["doc_idx"] for item in hybrid_results[:DISPLAY_TOP_K]}

    print("\nComparison")
    print(f"BM25/vector overlap: {len(bm25_top & vector_top)}/{DISPLAY_TOP_K}")
    print(f"Hybrid overlap with BM25: {len(hybrid_top & bm25_top)}/{DISPLAY_TOP_K}")
    print(f"Hybrid overlap with vector search: {len(hybrid_top & vector_top)}/{DISPLAY_TOP_K}")
    print(
        "BM25 favors exact token matches in titles and abstracts. Vector search favors "
        "semantic similarity. RRF promotes papers that rank well in either list and "
        "especially papers that appear in both."
    )


def main() -> None:
    configure_output_encoding()

    df = pd.read_parquet(DATA_FILE).reset_index(drop=True)
    bm25 = build_bm25_index(df)

    pc = Pinecone(api_key=get_api_key())
    index = pc.Index(INDEX_NAME)
    model, device = load_model()

    for query in QUERIES:
        print(f"\n{'=' * 80}")
        print(f"Query: {query}")

        bm25_results = bm25_search(bm25, query)
        vector_results = vector_search(index, model, query, device)
        hybrid_results = reciprocal_rank_fusion([bm25_results, vector_results])

        print_results("BM25 top-5", df, bm25_results, "BM25")
        print_results("Vector search top-5", df, vector_results, "vector")
        print_results("Hybrid RRF top-5", df, hybrid_results, "RRF")
        compare_methods(bm25_results, vector_results, hybrid_results)


if __name__ == "__main__":
    main()
