from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient
from tqdm import tqdm


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = PROJECT_ROOT / "dataset" / "dataset.csv"
DB_NAME = "spotify"
BATCH_SIZE = 1000


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    mongo_uri = require_env("MONGO_URI")

    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV file not found: {CSV_PATH}")

    df = pd.read_csv(CSV_PATH)
    df = df.drop(columns=[col for col in df.columns if col.startswith("Unnamed:")], errors="ignore")

    required_cols = [
        "track_id",
        "artists",
        "album_name",
        "track_name",
        "popularity",
        "duration_ms",
        "explicit",
        "danceability",
        "energy",
        "key",
        "loudness",
        "mode",
        "speechiness",
        "acousticness",
        "instrumentalness",
        "liveness",
        "valence",
        "tempo",
        "time_signature",
        "track_genre",
    ]
    missing_cols = sorted(set(required_cols) - set(df.columns))
    if missing_cols:
        raise ValueError(f"CSV is missing required columns: {missing_cols}")

    df = df.dropna(subset=["track_id", "artists", "track_name"])
    df["explicit"] = df["explicit"].map(lambda value: str(value).strip().lower() == "true")

    int_cols = ["popularity", "duration_ms", "key", "mode", "time_signature"]
    for col in int_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    float_cols = [
        "danceability",
        "energy",
        "loudness",
        "speechiness",
        "acousticness",
        "instrumentalness",
        "liveness",
        "valence",
        "tempo",
    ]
    for col in float_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(float)

    records = df.where(pd.notnull(df), None).to_dict("records")

    client = MongoClient(mongo_uri)
    db = client[DB_NAME]

    db["tracks_raw"].drop()

    print(f"Loading {len(records)} tracks into {DB_NAME}.tracks_raw...")
    for start in tqdm(range(0, len(records), BATCH_SIZE)):
        batch = records[start : start + BATCH_SIZE]
        if batch:
            db["tracks_raw"].insert_many(batch)

    print(f"Loaded documents: {db['tracks_raw'].count_documents({})}")
    print("Sample raw document:")
    print(db["tracks_raw"].find_one())

    client.close()


if __name__ == "__main__":
    main()
