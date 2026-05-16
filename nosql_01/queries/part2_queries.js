const spotify = db.getSiblingDB("spotify");
const tracks = spotify.tracks;

function printSection(title) {
  print(`\n=== ${title} ===`);
}

printSection("Task 1. Party tracks");
printjson(
  tracks
    .find(
      {
        "audio_features.danceability": { $gt: 0.7 },
        "audio_features.energy": { $gt: 0.7 },
        duration_ms: { $gte: 180000, $lte: 300000 }
      },
      {
        _id: 0,
        track_name: 1,
        artists: 1,
        track_genre: 1,
        popularity: 1,
        duration_ms: 1,
        "audio_features.danceability": 1,
        "audio_features.energy": 1
      }
    )
    .sort({ popularity: -1, track_name: 1 })
    .limit(20)
    .toArray()
);

printSection("Task 2. Artists whose every track is popular");
printjson(
  tracks
    .aggregate([
      { $unwind: "$artists" },
      {
        $group: {
          _id: "$artists",
          track_count: { $sum: 1 },
          min_popularity: { $min: "$popularity" },
          avg_popularity: { $avg: "$popularity" }
        }
      },
      {
        $match: {
          track_count: { $gte: 3 },
          min_popularity: { $gte: 60 }
        }
      },
      {
        $project: {
          _id: 0,
          artist: "$_id",
          track_count: 1,
          min_popularity: 1,
          avg_popularity: { $round: ["$avg_popularity", 1] }
        }
      },
      { $sort: { avg_popularity: -1, track_count: -1, artist: 1 } },
      { $limit: 20 }
    ])
    .toArray()
);

printSection("Task 3. Tempo outliers by genre");
printjson(
  tracks
    .aggregate([
      {
        $match: {
          track_genre: { $ne: null },
          "audio_features.tempo": { $type: "number" }
        }
      },
      {
        $group: {
          _id: "$track_genre",
          avg_tempo: { $avg: "$audio_features.tempo" },
          std_tempo: { $stdDevPop: "$audio_features.tempo" },
          tracks: {
            $push: {
              _id: "$_id",
              track_name: "$track_name",
              popularity: "$popularity",
              artists: "$artists",
              audio_features: {
                tempo: "$audio_features.tempo"
              }
            }
          }
        }
      },
      {
        $set: {
          outlier_threshold: {
            $add: ["$avg_tempo", { $multiply: [2, "$std_tempo"] }]
          }
        }
      },
      {
        $project: {
          _id: 0,
          genre: "$_id",
          avg_tempo: { $round: ["$avg_tempo", 1] },
          outlier_threshold: { $round: ["$outlier_threshold", 1] },
          outlier_tracks: {
            $filter: {
              input: "$tracks",
              as: "track",
              cond: {
                $gt: ["$$track.audio_features.tempo", "$outlier_threshold"]
              }
            }
          }
        }
      },
      { $match: { "outlier_tracks.0": { $exists: true } } },
      { $sort: { genre: 1 } }
    ])
    .toArray()
);

printSection("Task 4. Background work tracks");
printjson(
  tracks
    .find(
      {
        explicit: false,
        "audio_features.loudness": { $lt: -10 },
        "audio_features.speechiness": { $lt: 0.1 },
        "audio_features.instrumentalness": { $gt: 0.5 }
      },
      {
        _id: 0,
        track_name: 1,
        artists: 1,
        track_genre: 1,
        popularity: 1,
        explicit: 1,
        "audio_features.loudness": 1,
        "audio_features.speechiness": 1,
        "audio_features.instrumentalness": 1
      }
    )
    .sort({
      "audio_features.instrumentalness": -1,
      "audio_features.speechiness": 1,
      popularity: -1
    })
    .limit(20)
    .toArray()
);
