import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from dotenv import load_dotenv
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer


PROJECT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_DIR / ".env"
DATA_FILE = PROJECT_DIR / "data" / "arxiv_subset.parquet"
EMBEDDINGS_FILE = PROJECT_DIR / "embeddings" / "embeddings.npy"
MODEL_DIR = PROJECT_DIR / "assets" / "specter2_base"
MODEL_NAME = "allenai/specter2_base"

INDEX_NAME = "arxiv-papers"
TOP_K = 5
QUERY = "teaching machines to recognize objects in pictures"
RL_QUERY = "reinforcement learning agents learning from rewards"
RECENT_YEAR = datetime.now().year - 5
OLD_YEAR_CUTOFF = 2015


def get_api_key() -> str:
    load_dotenv(ENV_FILE)
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        raise RuntimeError(f"PINECONE_API_KEY is missing in {ENV_FILE}")
    return api_key


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


def get_matches(response) -> list:
    matches = getattr(response, "matches", None)
    if matches is not None:
        return list(matches)
    return list(response.get("matches", []))


def get_match_value(match, key: str, default=None):
    if isinstance(match, dict):
        return match.get(key, default)
    return getattr(match, key, default)


def print_pinecone_results(title: str, response) -> None:
    print(f"\n{title}")
    matches = get_matches(response)
    if not matches:
        print("No results found.")
        return

    for rank, match in enumerate(matches, start=1):
        score = get_match_value(match, "score", 0.0)
        metadata = get_match_value(match, "metadata", {}) or {}
        paper_title = metadata.get("title", "")
        category = metadata.get("category", "")
        year = metadata.get("year", "")
        abstract = metadata.get("abstract", "")

        print(f"{rank}. {paper_title}")
        print(f"   score={score:.4f} | category={category} | year={year}")
        print(f"   {abstract[:300]}...")


def pinecone_match_positions(response) -> list[int]:
    positions = []
    for match in get_matches(response):
        match_id = get_match_value(match, "id", "")
        if match_id.startswith("paper_"):
            positions.append(int(match_id.replace("paper_", "")))
    return positions


def pinecone_search(index, query_embedding: np.ndarray, top_k: int = TOP_K, filter_query=None):
    return index.query(
        vector=query_embedding.tolist(),
        top_k=top_k,
        include_metadata=True,
        filter=filter_query,
    )


def validate_local_inputs(df: pd.DataFrame, embeddings: np.ndarray) -> None:
    if embeddings.ndim != 2:
        raise ValueError(f"Expected 2D embeddings array, got shape {embeddings.shape}")
    if len(df) != len(embeddings):
        raise ValueError(f"Dataset rows ({len(df)}) do not match embeddings ({len(embeddings)})")


def normalize_rows(values: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return values / norms


def cosine_top_indices(embeddings: np.ndarray, query_embedding: np.ndarray, top_k: int = TOP_K) -> np.ndarray:
    normalized_embeddings = normalize_rows(embeddings.astype(np.float32))
    normalized_query = query_embedding / max(np.linalg.norm(query_embedding), 1e-12)
    cosine_scores = normalized_embeddings @ normalized_query
    return np.argsort(-cosine_scores)[:top_k]


def compare_pinecone_with_local_cosine(
    pinecone_response,
    embeddings: np.ndarray,
    query_embedding: np.ndarray,
) -> None:
    pinecone_positions = pinecone_match_positions(pinecone_response)
    local_positions = cosine_top_indices(embeddings, query_embedding).tolist()
    overlap = len(set(pinecone_positions) & set(local_positions))

    print("\nPinecone vs local cosine comparison")
    print(f"Pinecone top-{TOP_K} ids: {[f'paper_{idx}' for idx in pinecone_positions]}")
    print(f"Local cosine top-{TOP_K} ids: {[f'paper_{idx}' for idx in local_positions]}")
    print(f"Overlap: {overlap}/{TOP_K}")
    if overlap < TOP_K:
        print(
            "A small difference is possible when scores are very close, because Pinecone "
            "uses a vector index while the local calculation scans the whole NumPy array."
        )


def print_local_results(title: str, df: pd.DataFrame, indices: np.ndarray, scores: np.ndarray) -> None:
    print(f"\n{title}")
    for rank, idx in enumerate(indices, start=1):
        row = df.iloc[int(idx)]
        print(f"{rank}. {row['title']}")
        print(f"   score={scores[int(idx)]:.4f} | category={row['category']} | year={row['year']}")
        print(f"   {str(row['abstract'])[:300]}...")


def compare_local_metrics(df: pd.DataFrame, embeddings: np.ndarray, query_embedding: np.ndarray) -> None:
    validate_local_inputs(df, embeddings)

    embeddings = embeddings.astype(np.float32)
    normalized_embeddings = normalize_rows(embeddings)
    normalized_query = query_embedding / max(np.linalg.norm(query_embedding), 1e-12)

    cosine_scores = normalized_embeddings @ normalized_query
    dot_scores = embeddings @ query_embedding
    l2_distances = np.linalg.norm(embeddings - query_embedding, axis=1)

    cosine_top = np.argsort(-cosine_scores)[:TOP_K]
    dot_top = np.argsort(-dot_scores)[:TOP_K]
    l2_top = np.argsort(l2_distances)[:TOP_K]

    print_local_results("Local cosine similarity top-5", df, cosine_top, cosine_scores)
    print_local_results("Local dot product top-5", df, dot_top, dot_scores)
    print_local_results("Local L2 distance top-5 (lower is better)", df, l2_top, l2_distances)

    if np.array_equal(cosine_top, dot_top) and np.array_equal(cosine_top, l2_top):
        print(
            "\nMetric comparison: the top-5 lists are identical because embeddings and "
            "the query are normalized. For unit vectors, cosine and dot product rank "
            "the same way, while L2 distance ranks in the opposite direction of cosine."
        )
    else:
        print(
            "\nMetric comparison: the metrics differ because they emphasize different "
            "geometry. Cosine compares direction, dot product also depends on vector "
            "length, and L2 distance measures absolute distance."
        )


def explain_filters(df: pd.DataFrame) -> None:
    recent_count = len(df[(df["category"] == "cs.LG") & (df["year"] >= RECENT_YEAR)])
    old_count = len(df[df["year"] < OLD_YEAR_CUTOFF])

    print("\nFilter comparison")
    print(
        f"Filter A uses category='cs.LG' and year >= {RECENT_YEAR}. "
        f"This dataset has {recent_count} matching local rows."
    )
    print(
        f"Filter B uses year < {OLD_YEAR_CUTOFF} across all categories. "
        f"This dataset has {old_count} matching local rows."
    )
    print(
        "Therefore filter A is much stricter and may return no Pinecone matches, "
        "while filter B searches almost the whole current subset."
    )


def main() -> None:
    pc = Pinecone(api_key=get_api_key())
    index = pc.Index(INDEX_NAME)
    model, device = load_model()

    df = pd.read_parquet(DATA_FILE)
    embeddings = np.load(EMBEDDINGS_FILE)
    validate_local_inputs(df, embeddings)

    query_embedding = encode_query(model, QUERY, device)
    semantic_response = pinecone_search(index, query_embedding)
    print_pinecone_results(f"Pure semantic search: {QUERY}", semantic_response)
    compare_pinecone_with_local_cosine(semantic_response, embeddings, query_embedding)

    rl_embedding = encode_query(model, RL_QUERY, device)
    recent_filter = {"category": {"$eq": "cs.LG"}, "year": {"$gte": RECENT_YEAR}}
    old_filter = {"year": {"$lt": OLD_YEAR_CUTOFF}}

    recent_response = pinecone_search(index, rl_embedding, filter_query=recent_filter)
    print_pinecone_results(
        f"Filtered search A: reinforcement learning, category cs.LG, year >= {RECENT_YEAR}",
        recent_response,
    )

    old_response = pinecone_search(index, query_embedding, filter_query=old_filter)
    print_pinecone_results(
        f"Filtered search B: older papers, year < {OLD_YEAR_CUTOFF}, any category",
        old_response,
    )
    explain_filters(df)

    compare_local_metrics(df, embeddings, query_embedding)


if __name__ == "__main__":
    main()
