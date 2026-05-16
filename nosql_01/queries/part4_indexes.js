const spotify = db.getSiblingDB("spotify");
const tracks = spotify.tracks;

function printSection(title) {
  print(`\n=== ${title} ===`);
}

function getWinningPlan(explain) {
  const winningPlan = explain.queryPlanner.winningPlan;
  return winningPlan.queryPlan || winningPlan;
}

function collectStageNames(node, names = []) {
  if (!node || typeof node !== "object") {
    return names;
  }

  if (node.stage) {
    names.push(node.stage);
  }

  for (const value of Object.values(node)) {
    if (Array.isArray(value)) {
      value.forEach((item) => collectStageNames(item, names));
    } else if (value && typeof value === "object") {
      collectStageNames(value, names);
    }
  }

  return [...new Set(names)];
}

function collectIndexNames(node, names = []) {
  if (!node || typeof node !== "object") {
    return names;
  }

  if (node.indexName) {
    names.push(node.indexName);
  }

  for (const value of Object.values(node)) {
    if (Array.isArray(value)) {
      value.forEach((item) => collectIndexNames(item, names));
    } else if (value && typeof value === "object") {
      collectIndexNames(value, names);
    }
  }

  return [...new Set(names)];
}

function explainSummary(label, explain) {
  const plan = getWinningPlan(explain);
  print(`\n${label}`);
  printjson({
    nReturned: explain.executionStats.nReturned,
    totalKeysExamined: explain.executionStats.totalKeysExamined,
    totalDocsExamined: explain.executionStats.totalDocsExamined,
    executionTimeMillis: explain.executionStats.executionTimeMillis,
    winningStages: collectStageNames(plan),
    indexesUsed: collectIndexNames(plan),
    winningPlan: plan
  });
}

printSection("Task 1. Query before and after compound index");
tracks.dropIndexes();

const partyPopFilter = {
  track_genre: "pop",
  "audio_features.danceability": { $gte: 0.7 }
};
const partyPopSort = { popularity: -1 };

const beforeTask1 = tracks.find(partyPopFilter).sort(partyPopSort).explain("executionStats");
explainSummary("Before index", beforeTask1);

tracks.createIndex(
  {
    track_genre: 1,
    popularity: -1,
    "audio_features.danceability": 1
  },
  { name: "idx_tracks_genre_popularity_danceability" }
);

const afterTask1 = tracks.find(partyPopFilter).sort(partyPopSort).explain("executionStats");
explainSummary("After index", afterTask1);

printSection("Task 2. Work music compound index");
const workMusicFilter = {
  explicit: false,
  "audio_features.instrumentalness": { $gt: 0.5 },
  "audio_features.speechiness": { $lt: 0.1 }
};

const beforeTask2 = tracks.find(workMusicFilter).explain("executionStats");
explainSummary("Before work-music index", beforeTask2);

tracks.createIndex(
  {
    explicit: 1,
    "audio_features.instrumentalness": -1,
    "audio_features.speechiness": 1
  },
  { name: "idx_tracks_work_music" }
);

const afterTask2 = tracks.find(workMusicFilter).explain("executionStats");
explainSummary("After work-music index", afterTask2);

printSection("Task 3. Covered query check");
const popularityFilter = {
  track_genre: "pop",
  popularity: { $gte: 70 }
};

const originalExplain = tracks.find(popularityFilter).explain("executionStats");
explainSummary("Original query without projection", originalExplain);

const coveredVariantExplain = tracks
  .find(popularityFilter, {
    _id: 0,
    track_genre: 1,
    popularity: 1,
    "audio_features.danceability": 1
  })
  .explain("executionStats");
explainSummary("Covered variant with projection", coveredVariantExplain);

print(
  "The original query is not covered because it returns full documents. " +
    "A covered query must filter and project only indexed fields and exclude _id unless _id is in the index."
);
