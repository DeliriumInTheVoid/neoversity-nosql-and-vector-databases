const spotify = db.getSiblingDB("spotify");
const tracks = spotify.tracks;

function printSection(title) {
  print(`\n=== ${title} ===`);
}

printSection("Task 1. Top 10 artists by average popularity");
printjson(
  tracks
    .aggregate([
      { $unwind: "$artists" },
      {
        $group: {
          _id: "$artists",
          track_count: { $sum: 1 },
          avg_popularity: { $avg: "$popularity" }
        }
      },
      { $match: { track_count: { $gte: 5 } } },
      {
        $project: {
          _id: 0,
          artist: "$_id",
          track_count: 1,
          avg_popularity: { $round: ["$avg_popularity", 1] }
        }
      },
      { $sort: { avg_popularity: -1, track_count: -1, artist: 1 } },
      { $limit: 10 }
    ])
    .toArray()
);

printSection("Task 2. Mood distribution");
printjson(
  tracks
    .aggregate([
      {
        $addFields: {
          mood: {
            $switch: {
              branches: [
                {
                  case: {
                    $and: [
                      { $gte: ["$audio_features.valence", 0.5] },
                      { $gte: ["$audio_features.energy", 0.5] }
                    ]
                  },
                  then: "happy"
                },
                {
                  case: {
                    $and: [
                      { $lt: ["$audio_features.valence", 0.5] },
                      { $gte: ["$audio_features.energy", 0.5] }
                    ]
                  },
                  then: "angry"
                },
                {
                  case: {
                    $and: [
                      { $gte: ["$audio_features.valence", 0.5] },
                      { $lt: ["$audio_features.energy", 0.5] }
                    ]
                  },
                  then: "calm"
                }
              ],
              default: "sad"
            }
          }
        }
      },
      {
        $group: {
          _id: "$mood",
          track_count: { $sum: 1 }
        }
      },
      {
        $addFields: {
          sort_order: {
            $switch: {
              branches: [
                { case: { $eq: ["$_id", "happy"] }, then: 1 },
                { case: { $eq: ["$_id", "angry"] }, then: 2 },
                { case: { $eq: ["$_id", "calm"] }, then: 3 }
              ],
              default: 4
            }
          }
        }
      },
      { $sort: { sort_order: 1 } },
      {
        $project: {
          _id: 0,
          mood: "$_id",
          track_count: 1
        }
      }
    ])
    .toArray()
);

printSection("Task 3. Most danceable genre with sample tracks");
printjson(
  tracks
    .aggregate([
      {
        $group: {
          _id: "$track_genre",
          track_count: { $sum: 1 },
          avg_danceability: { $avg: "$audio_features.danceability" },
          avg_energy: { $avg: "$audio_features.energy" },
          avg_valence: { $avg: "$audio_features.valence" }
        }
      },
      { $match: { track_count: { $gte: 100 } } },
      {
        $project: {
          _id: 0,
          genre: "$_id",
          track_count: 1,
          avg_danceability: { $round: ["$avg_danceability", 3] },
          avg_energy: { $round: ["$avg_energy", 3] },
          avg_valence: { $round: ["$avg_valence", 3] }
        }
      },
      { $sort: { avg_danceability: -1, avg_energy: -1, avg_valence: -1 } },
      { $limit: 1 },
      {
        $lookup: {
          from: "tracks",
          let: { genre: "$genre" },
          pipeline: [
            {
              $match: {
                $expr: { $eq: ["$track_genre", "$$genre"] }
              }
            },
            { $sort: { "audio_features.danceability": -1, popularity: -1 } },
            { $limit: 5 },
            {
              $project: {
                _id: 0,
                track_name: 1,
                artists: 1,
                popularity: 1,
                danceability: "$audio_features.danceability"
              }
            }
          ],
          as: "sample_tracks"
        }
      }
    ])
    .toArray()
);
