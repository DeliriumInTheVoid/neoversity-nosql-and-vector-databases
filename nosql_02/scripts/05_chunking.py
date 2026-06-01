import os
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer
from tqdm import tqdm


PROJECT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_DIR / ".env"
DATA_FILE = PROJECT_DIR / "data" / "arxiv_subset.parquet"
MODEL_DIR = PROJECT_DIR / "assets" / "specter2_base"
MODEL_NAME = "allenai/specter2_base"

FIXED_INDEX_NAME = "arxiv-chunks-fixed"
SEMANTIC_INDEX_NAME = "arxiv-chunks-semantic"
VECTOR_DIM = 768
METRIC = "cosine"
DEFAULT_CLOUD = "aws"
DEFAULT_REGION = "us-east-1"

NUM_ARTICLES = 30
FIXED_CHUNK_WORDS = 120
FIXED_CHUNK_OVERLAP = 30
SEMANTIC_MAX_WORDS = 120
ENCODE_BATCH_SIZE = 128
UPSERT_BATCH_SIZE = 200
TOP_K = 5

TEST_QUERIES = [
    "gamma ray bursts and supernova explosions",
    "neutron stars and x ray timing observations",
    "machine learning methods for scientific data",
]


def get_api_key() -> str:
    load_dotenv(ENV_FILE)
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        raise RuntimeError(f"PINECONE_API_KEY is missing in {ENV_FILE}")
    return api_key


def is_index_ready(description) -> bool:
    status = getattr(description, "status", {}) or {}
    if isinstance(status, dict):
        return bool(status.get("ready"))
    return bool(getattr(status, "ready", False))


def wait_until_ready(pc: Pinecone, index_name: str) -> None:
    while True:
        description = pc.describe_index(index_name)
        if is_index_ready(description):
            return
        print(f"Waiting for Pinecone index '{index_name}' to become ready...")
        time.sleep(5)


def create_index_if_needed(pc: Pinecone, index_name: str) -> None:
    existing_indexes = pc.list_indexes().names()
    if index_name in existing_indexes:
        print(f"Pinecone index '{index_name}' already exists.")
        description = pc.describe_index(index_name)
        dimension = getattr(description, "dimension", None)
        if dimension is not None and int(dimension) != VECTOR_DIM:
            raise ValueError(f"Index '{index_name}' has dimension {dimension}, expected {VECTOR_DIM}")
        wait_until_ready(pc, index_name)
        return

    cloud = os.getenv("PINECONE_CLOUD", DEFAULT_CLOUD)
    region = os.getenv("PINECONE_REGION", DEFAULT_REGION)
    print(f"Creating Pinecone index '{index_name}' in {cloud}/{region}...")
    pc.create_index(
        name=index_name,
        dimension=VECTOR_DIM,
        metric=METRIC,
        spec=ServerlessSpec(cloud=cloud, region=region),
    )
    wait_until_ready(pc, index_name)


def clean_text(value, max_length: int | None = None) -> str:
    if pd.isna(value):
        return ""
    text = " ".join(str(value).split())
    if max_length is not None:
        return text[:max_length]
    return text


def word_count(text: str) -> int:
    return len(text.split())


def select_longest_articles(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["abstract_words"] = df["abstract"].fillna("").astype(str).str.split().str.len()
    return df.sort_values("abstract_words", ascending=False).head(NUM_ARTICLES).reset_index(drop=True)


def fixed_size_chunks(text: str, chunk_words: int = FIXED_CHUNK_WORDS, overlap: int = FIXED_CHUNK_OVERLAP) -> list[str]:
    words = clean_text(text).split()
    if not words:
        return []
    if chunk_words <= overlap:
        raise ValueError("chunk_words must be greater than overlap")

    chunks = []
    step = chunk_words - overlap
    for start in range(0, len(words), step):
        chunk = words[start : start + chunk_words]
        if chunk:
            chunks.append(" ".join(chunk))
        if start + chunk_words >= len(words):
            break
    return chunks


def split_sentences(text: str) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def semantic_chunks(text: str, max_words: int = SEMANTIC_MAX_WORDS) -> list[str]:
    sentences = split_sentences(text)
    if not sentences:
        return []

    chunks = []
    current_sentences = []
    current_words = 0

    for sentence in sentences:
        sentence_words = word_count(sentence)

        if sentence_words > max_words:
            if current_sentences:
                chunks.append(" ".join(current_sentences))
                current_sentences = []
                current_words = 0
            chunks.extend(fixed_size_chunks(sentence, chunk_words=max_words, overlap=0))
            continue

        if current_sentences and current_words + sentence_words > max_words:
            chunks.append(" ".join(current_sentences))
            current_sentences = [sentence]
            current_words = sentence_words
        else:
            current_sentences.append(sentence)
            current_words += sentence_words

    if current_sentences:
        chunks.append(" ".join(current_sentences))

    return chunks


def load_model() -> tuple[SentenceTransformer, str]:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    if device == "cuda":
        print(f"CUDA device: {torch.cuda.get_device_name(0)}")

    model_path = MODEL_DIR if MODEL_DIR.exists() else MODEL_NAME
    print(f"Loading model: {model_path}")
    model = SentenceTransformer(str(model_path), device=device)
    return model, device


def encode_texts(model: SentenceTransformer, texts: list[str], device: str) -> np.ndarray:
    embeddings = model.encode(
        texts,
        batch_size=ENCODE_BATCH_SIZE,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
        device=device,
    )
    return np.asarray(embeddings, dtype=np.float32)


def build_chunk_records(df: pd.DataFrame, strategy: str) -> list[dict]:
    records = []
    chunker = fixed_size_chunks if strategy == "fixed" else semantic_chunks

    for article_number, row in df.iterrows():
        chunks = chunker(row["abstract"])
        for chunk_number, chunk_text in enumerate(chunks):
            records.append(
                {
                    "id": f"{strategy}_{article_number}_{chunk_number}",
                    "text_for_embedding": f"{clean_text(row['title'])} [SEP] {chunk_text}",
                    "metadata": {
                        "arxiv_id": clean_text(row["id"], 100),
                        "title": clean_text(row["title"], 500),
                        "chunk_text": clean_text(chunk_text, 2000),
                        "chunk_number": int(chunk_number),
                        "year": int(row["year"]) if not pd.isna(row["year"]) else 0,
                        "category": clean_text(row["category"], 100),
                    },
                }
            )

    return records


def upsert_chunk_records(index, records: list[dict], embeddings: np.ndarray, label: str) -> None:
    if len(records) != len(embeddings):
        raise ValueError(f"Chunk records ({len(records)}) do not match embeddings ({len(embeddings)})")

    for start in tqdm(
        range(0, len(records), UPSERT_BATCH_SIZE),
        desc=f"Uploading {label} chunks",
        file=sys.stdout,
    ):
        end = min(start + UPSERT_BATCH_SIZE, len(records))
        vectors = [
            {
                "id": records[position]["id"],
                "values": embeddings[position].astype(float).tolist(),
                "metadata": records[position]["metadata"],
            }
            for position in range(start, end)
        ]
        index.upsert(vectors=vectors)


def print_index_count(index, index_name: str) -> None:
    stats = index.describe_index_stats()
    total_vector_count = getattr(stats, "total_vector_count", None)
    if total_vector_count is None and isinstance(stats, dict):
        total_vector_count = stats.get("total_vector_count", 0)
    print(f"Total vectors in '{index_name}': {total_vector_count}")


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


def search_chunks(index, model: SentenceTransformer, query: str, device: str, label: str) -> None:
    query_embedding = encode_query(model, query, device)
    response = index.query(
        vector=query_embedding.tolist(),
        top_k=TOP_K,
        include_metadata=True,
    )

    print(f"\n{label} chunks search: {query}")
    matches = sorted(
        get_matches(response),
        key=lambda match: get_match_value(match, "score", 0.0),
        reverse=True,
    )
    if not matches:
        print("No results found.")
        return

    for rank, match in enumerate(matches, start=1):
        score = get_match_value(match, "score", 0.0)
        metadata = get_match_value(match, "metadata", {}) or {}
        title = metadata.get("title", "")
        chunk_number = metadata.get("chunk_number", "")
        category = metadata.get("category", "")
        year = metadata.get("year", "")
        chunk_text = metadata.get("chunk_text", "")

        print(f"{rank}. {title}")
        print(f"   score={score:.4f} | chunk={chunk_number} | category={category} | year={year}")
        print(f"   {chunk_text[:350]}...")


def main() -> None:
    df = pd.read_parquet(DATA_FILE)
    selected_df = select_longest_articles(df)
    print(f"Selected {len(selected_df)} articles with the longest abstracts.")
    print(
        "Longest abstract word counts:",
        selected_df["abstract_words"].head(10).astype(int).tolist(),
    )

    model, device = load_model()
    pc = Pinecone(api_key=get_api_key())

    create_index_if_needed(pc, FIXED_INDEX_NAME)
    create_index_if_needed(pc, SEMANTIC_INDEX_NAME)
    fixed_index = pc.Index(FIXED_INDEX_NAME)
    semantic_index = pc.Index(SEMANTIC_INDEX_NAME)

    fixed_records = build_chunk_records(selected_df, "fixed")
    semantic_records = build_chunk_records(selected_df, "semantic")
    print(f"Fixed-size chunks created: {len(fixed_records)}")
    print(f"Semantic chunks created: {len(semantic_records)}")

    fixed_embeddings = encode_texts(model, [record["text_for_embedding"] for record in fixed_records], device)
    semantic_embeddings = encode_texts(
        model,
        [record["text_for_embedding"] for record in semantic_records],
        device,
    )

    upsert_chunk_records(fixed_index, fixed_records, fixed_embeddings, "fixed-size")
    upsert_chunk_records(semantic_index, semantic_records, semantic_embeddings, "semantic")
    print_index_count(fixed_index, FIXED_INDEX_NAME)
    print_index_count(semantic_index, SEMANTIC_INDEX_NAME)

    for query in TEST_QUERIES:
        search_chunks(fixed_index, model, query, device, "Fixed-size")
        search_chunks(semantic_index, model, query, device, "Semantic")


if __name__ == "__main__":
    main()
