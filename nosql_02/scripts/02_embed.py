from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_FILE = PROJECT_DIR / "data" / "arxiv_subset.parquet"
MODEL_DIR = PROJECT_DIR / "assets" / "specter2_base"
OUTPUT_DIR = PROJECT_DIR / "embeddings"
OUTPUT_FILE = OUTPUT_DIR / "embeddings.npy"
CPU_BATCH_SIZE = 64
GPU_BATCH_SIZE = 256


def build_texts(df: pd.DataFrame) -> list[str]:
    required_columns = {"title", "abstract"}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required columns in dataset: {missing}")

    titles = df["title"].fillna("").astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    abstracts = df["abstract"].fillna("").astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    return (titles + " [SEP] " + abstracts).tolist()


def main() -> None:
    df = pd.read_parquet(DATA_FILE)
    texts = build_texts(df)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    batch_size = GPU_BATCH_SIZE if device == "cuda" else CPU_BATCH_SIZE

    print(f"Using device: {device}")
    if device == "cuda":
        print(f"CUDA device: {torch.cuda.get_device_name(0)}")
        print(f"CUDA version: {torch.version.cuda}")
    else:
        print("CUDA is not available; using CPU.")

    model = SentenceTransformer(str(MODEL_DIR), device=device)
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
        device=device,
    )

    embeddings = np.asarray(embeddings, dtype=np.float32)
    first_embedding_norm = np.linalg.norm(embeddings[0]) if len(embeddings) else 0.0

    print(f"Total processed texts: {len(texts)}")
    print(f"Embedding dimension: {embeddings.shape[1] if embeddings.ndim == 2 else 0}")
    print(f"First embedding norm: {first_embedding_norm:.6f}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    np.save(OUTPUT_FILE, embeddings)
    print(f"Saved embeddings to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
