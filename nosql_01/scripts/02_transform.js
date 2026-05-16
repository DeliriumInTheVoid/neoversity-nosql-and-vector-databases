const spotify = db.getSiblingDB("spotify");

spotify.tracks.drop();

const sourceCount = spotify.tracks_raw.countDocuments();
print(`Source documents in tracks_raw: ${sourceCount}`);

spotify.tracks_raw.aggregate([
  {
    $project: {
      track_id: 1,
      track_name: 1,
      album_name: 1,
      explicit: {
        $cond: [
          { $in: ["$explicit", [true, "True", "true", 1, "1"]] },
          true,
          false
        ]
      },
      popularity: { $toInt: "$popularity" },
      duration_ms: { $toInt: "$duration_ms" },
      track_genre: 1,
      artists_raw: "$artists",
      danceability: { $toDouble: "$danceability" },
      energy: { $toDouble: "$energy" },
      loudness: { $toDouble: "$loudness" },
      speechiness: { $toDouble: "$speechiness" },
      acousticness: { $toDouble: "$acousticness" },
      instrumentalness: { $toDouble: "$instrumentalness" },
      liveness: { $toDouble: "$liveness" },
      valence: { $toDouble: "$valence" },
      tempo: { $toDouble: "$tempo" },
      key: { $toInt: "$key" },
      mode: { $toInt: "$mode" },
      time_signature: { $toInt: "$time_signature" }
    }
  },
  {
    $addFields: {
      artists: {
        $filter: {
          input: {
            $map: {
              input: { $split: [{ $ifNull: ["$artists_raw", ""] }, ";"] },
              as: "artist",
              in: { $trim: { input: "$$artist" } }
            }
          },
          as: "artist",
          cond: { $ne: ["$$artist", ""] }
        }
      },
      audio_features: {
        danceability: "$danceability",
        energy: "$energy",
        loudness: "$loudness",
        speechiness: "$speechiness",
        acousticness: "$acousticness",
        instrumentalness: "$instrumentalness",
        liveness: "$liveness",
        valence: "$valence",
        tempo: "$tempo",
        key: "$key",
        mode: "$mode",
        time_signature: "$time_signature"
      },
      duration_sec: {
        $round: [{ $divide: ["$duration_ms", 1000] }, 1]
      },
      popularity_tier: {
        $switch: {
          branches: [
            { case: { $gte: ["$popularity", 70] }, then: "high" },
            { case: { $gte: ["$popularity", 40] }, then: "medium" }
          ],
          default: "low"
        }
      }
    }
  },
  {
    $project: {
      artists_raw: 0,
      danceability: 0,
      energy: 0,
      loudness: 0,
      speechiness: 0,
      acousticness: 0,
      instrumentalness: 0,
      liveness: 0,
      valence: 0,
      tempo: 0,
      key: 0,
      mode: 0,
      time_signature: 0
    }
  },
  { $out: "tracks" }
]);

print(`Transformed documents in tracks: ${spotify.tracks.countDocuments()}`);
print("Sample transformed document:");
printjson(spotify.tracks.findOne());
