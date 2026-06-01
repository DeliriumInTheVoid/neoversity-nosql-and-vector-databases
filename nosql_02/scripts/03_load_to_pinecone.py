import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from tqdm import tqdm


PROJECT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_DIR / ".env"
DATA_FILE = PROJECT_DIR / "data" / "arxiv_subset.parquet"
EMBEDDINGS_FILE = PROJECT_DIR / "embeddings" / "embeddings.npy"

INDEX_NAME = "arxiv-papers"
VECTOR_DIM = 768
BATCH_SIZE = 200
METRIC = "cosine"
DEFAULT_CLOUD = "aws"
DEFAULT_REGION = "us-east-1"


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


def create_index_if_needed(pc: Pinecone) -> None:
    existing_indexes = pc.list_indexes().names()
    if INDEX_NAME in existing_indexes:
        print(f"Pinecone index '{INDEX_NAME}' already exists.")
        description = pc.describe_index(INDEX_NAME)
        dimension = getattr(description, "dimension", None)
        if dimension is not None and int(dimension) != VECTOR_DIM:
            raise ValueError(
                f"Index '{INDEX_NAME}' has dimension {dimension}, expected {VECTOR_DIM}"
            )
        wait_until_ready(pc, INDEX_NAME)
        return

    cloud = os.getenv("PINECONE_CLOUD", DEFAULT_CLOUD)
    region = os.getenv("PINECONE_REGION", DEFAULT_REGION)
    print(f"Creating Pinecone index '{INDEX_NAME}' in {cloud}/{region}...")
    pc.create_index(
        name=INDEX_NAME,
        dimension=VECTOR_DIM,
        metric=METRIC,
        spec=ServerlessSpec(cloud=cloud, region=region),
    )
    wait_until_ready(pc, INDEX_NAME)


def clean_text(value, max_length: int) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).split())[:max_length]


def clean_year(value) -> int:
    if pd.isna(value):
        return 0
    return int(value)


def build_vector(record: pd.Series, embedding: np.ndarray, number: int) -> dict:
    return {
        "id": f"paper_{number}",
        "values": embedding.astype(float).tolist(),
        "metadata": {
            "arxiv_id": clean_text(record["id"], 100),
            "title": clean_text(record["title"], 500),
            "abstract": clean_text(record["abstract"], 500),
            "authors": clean_text(record["authors"], 200),
            "year": clean_year(record["year"]),
            "category": clean_text(record["category"], 100),
        },
    }


def validate_inputs(df: pd.DataFrame, embeddings: np.ndarray) -> None:
    required_columns = {"id", "title", "abstract", "authors", "year", "category"}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required columns in dataset: {missing}")

    if embeddings.ndim != 2:
        raise ValueError(f"Expected 2D embeddings array, got shape {embeddings.shape}")
    if embeddings.shape[1] != VECTOR_DIM:
        raise ValueError(f"Expected embedding dimension {VECTOR_DIM}, got {embeddings.shape[1]}")
    if len(df) != len(embeddings):
        raise ValueError(f"Dataset rows ({len(df)}) do not match embeddings ({len(embeddings)})")


def main() -> None:
    pc = Pinecone(api_key=get_api_key())
    create_index_if_needed(pc)
    index = pc.Index(INDEX_NAME)

    df = pd.read_parquet(DATA_FILE)
    embeddings = np.load(EMBEDDINGS_FILE)
    validate_inputs(df, embeddings)

    for start in tqdm(range(0, len(df), BATCH_SIZE), desc="Uploading to Pinecone", file=sys.stdout):
        end = min(start + BATCH_SIZE, len(df))
        vectors = [
            build_vector(record, embeddings[position], position)
            for position, (_, record) in enumerate(df.iloc[start:end].iterrows(), start=start)
        ]
        index.upsert(vectors=vectors)

    stats = index.describe_index_stats()
    total_vector_count = getattr(stats, "total_vector_count", None)
    if total_vector_count is None and isinstance(stats, dict):
        total_vector_count = stats.get("total_vector_count", 0)

    print(f"Total vectors in index: {total_vector_count}", flush=True)


if __name__ == "__main__":
    main()
