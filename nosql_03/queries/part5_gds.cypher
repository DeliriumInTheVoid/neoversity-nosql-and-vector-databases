// 5.1. PageRank on a movie similarity graph
// Cleanup for repeatable runs
CALL gds.graph.drop('movieGraph', false) YIELD graphName
RETURN 'Dropped old projection' AS action, graphName;

MATCH ()-[co:CO_RATED]-()
DELETE co;

// Step 1: materialize movie-movie edges through users who rated both movies highly.
MATCH (m1:Movie)<-[r1:RATED]-(u:User)-[r2:RATED]->(m2:Movie)
WHERE r1.rating >= 4
  AND r2.rating >= 4
  AND id(m1) < id(m2)
WITH m1, m2, count(u) AS weight
WHERE count { (m1)<-[:RATED]-(:User) } > 20
  AND count { (m2)<-[:RATED]-(:User) } > 20
WITH m1, m2, weight
ORDER BY weight DESC
LIMIT 50000
MERGE (m1)-[co:CO_RATED]-(m2)
SET co.weight = weight;

// Step 2: create an in-memory GDS projection.
CALL gds.graph.project(
  'movieGraph',
  'Movie',
  { CO_RATED: { orientation: 'UNDIRECTED', properties: 'weight' } }
)
YIELD graphName, nodeCount, relationshipCount
RETURN graphName, nodeCount, relationshipCount;

// Step 3: run weighted PageRank and inspect the top movies.
CALL gds.pageRank.stream(
  'movieGraph',
  {
    relationshipWeightProperty: 'weight',
    maxIterations: 20,
    dampingFactor: 0.85
  }
)
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS m, score
MATCH (m)<-[r:RATED]-(:User)
RETURN
  m.movieId AS movieId,
  m.title AS title,
  m.year AS year,
  round(score * 100000.0) / 100000.0 AS pageRank,
  count(r) AS ratingCount,
  round(avg(r.rating) * 100.0) / 100.0 AS avgRating
ORDER BY pageRank DESC
LIMIT 20;

// Step 4: drop the projection and delete temporary movie-movie edges.
CALL gds.graph.drop('movieGraph') YIELD graphName
RETURN 'Dropped projection' AS action, graphName;

MATCH ()-[co:CO_RATED]-()
DELETE co;

// 5.2. Louvain community detection on a user similarity graph
// Cleanup for repeatable runs
CALL gds.graph.drop('userSimilarity', false) YIELD graphName
RETURN 'Dropped old projection' AS action, graphName;

MATCH ()-[sim:SIMILAR]-()
DELETE sim;

// Step 1: materialize user-user edges through shared 5-star movies
// Very popular movies are capped out to avoid pair explosion
MATCH (m:Movie)<-[r:RATED]-(:User)
WHERE r.rating = 5
WITH m, count(r) AS fiveStarCount
WHERE fiveStarCount >= 20 AND fiveStarCount <= 500
MATCH (u1:User)-[r1:RATED]->(m)<-[r2:RATED]-(u2:User)
WHERE r1.rating = 5
  AND r2.rating = 5
  AND id(u1) < id(u2)
WITH u1, u2, count(m) AS weight
WHERE weight >= 2
WITH u1, u2, weight
ORDER BY weight DESC
LIMIT 30000
MERGE (u1)-[sim:SIMILAR]-(u2)
SET
  sim.weight = weight,
  sim.distance = 1.0 / toFloat(weight);

// Step 2: create an in-memory GDS projection
CALL gds.graph.project(
  'userSimilarity',
  'User',
  { SIMILAR: { orientation: 'UNDIRECTED', properties: ['weight', 'distance'] } }
)
YIELD graphName, nodeCount, relationshipCount
RETURN graphName, nodeCount, relationshipCount;

// Step 3: run Louvain and write the community id back to User nodes
CALL gds.louvain.write(
  'userSimilarity',
  {
    relationshipWeightProperty: 'weight',
    writeProperty: 'louvainCommunity'
  }
)
YIELD
  communityCount,
  modularity,
  modularities,
  ranLevels,
  nodePropertiesWritten
RETURN
  communityCount,
  round(modularity * 10000.0) / 10000.0 AS modularity,
  modularities,
  ranLevels,
  nodePropertiesWritten;

// Step 4a: show the 10 largest communities
MATCH (u:User)
WHERE u.louvainCommunity IS NOT NULL
RETURN
  u.louvainCommunity AS communityId,
  count(u) AS userCount
ORDER BY userCount DESC
LIMIT 10;

// Step 4b: for the 10 largest communities, find the top 3 genres liked by users
MATCH (u:User)
WHERE u.louvainCommunity IS NOT NULL
WITH u.louvainCommunity AS communityId, count(u) AS userCount
ORDER BY userCount DESC
LIMIT 10
MATCH (member:User)-[r:RATED]->(m:Movie)-[:HAS_GENRE]->(g:Genre)
WHERE member.louvainCommunity = communityId
  AND r.rating >= 4
WITH communityId, userCount, g.name AS genre, count(r) AS highRatings
ORDER BY communityId, highRatings DESC, genre
WITH communityId, userCount, collect({genre: genre, highRatings: highRatings})[0..3] AS topGenres
RETURN communityId, userCount, topGenres
ORDER BY userCount DESC;

// Step 5: drop the projection and delete temporary user-user edges
CALL gds.graph.drop('userSimilarity') YIELD graphName
RETURN 'Dropped projection' AS action, graphName;

MATCH ()-[sim:SIMILAR]-()
DELETE sim;

// 5.3. Dijkstra shortest paths on a user similarity graph
// Cleanup for repeatable runs
CALL gds.graph.drop('userGraph', false) YIELD graphName
RETURN 'Dropped old projection' AS action, graphName;

MATCH ()-[sim:SIMILAR]-()
DELETE sim;

// Recreate the same similarity graph. The distance property is inverse weight:
// stronger similarity means lower traversal cost for Dijkstra
MATCH (m:Movie)<-[r:RATED]-(:User)
WHERE r.rating = 5
WITH m, count(r) AS fiveStarCount
WHERE fiveStarCount >= 20 AND fiveStarCount <= 500
MATCH (u1:User)-[r1:RATED]->(m)<-[r2:RATED]-(u2:User)
WHERE r1.rating = 5
  AND r2.rating = 5
  AND id(u1) < id(u2)
WITH u1, u2, count(m) AS weight
WHERE weight >= 2
WITH u1, u2, weight
ORDER BY weight DESC
LIMIT 30000
MERGE (u1)-[sim:SIMILAR]-(u2)
SET
  sim.weight = weight,
  sim.distance = 1.0 / toFloat(weight);

CALL gds.graph.project(
  'userGraph',
  'User',
  { SIMILAR: { orientation: 'UNDIRECTED', properties: ['weight', 'distance'] } }
)
YIELD graphName, nodeCount, relationshipCount
RETURN graphName, nodeCount, relationshipCount;

// Dijkstra for one selected pair
MATCH (source:User {userId: 36}), (target:User {userId: 65})
CALL gds.shortestPath.dijkstra.stream(
  'userGraph',
  {
    sourceNode: source,
    targetNode: target,
    relationshipWeightProperty: 'distance'
  }
)
YIELD totalCost, nodeIds, costs
RETURN
  source.userId AS sourceUserId,
  target.userId AS targetUserId,
  size(nodeIds) - 1 AS hopCount,
  size(nodeIds) - 2 AS intermediateUsers,
  round(totalCost * 10000.0) / 10000.0 AS totalDistance,
  [nodeId IN nodeIds | gds.util.asNode(nodeId).userId] AS pathUsers,
  [cost IN costs | round(cost * 10000.0) / 10000.0] AS cumulativeCosts;

// Try several user pairs and compute the average shortest path length
UNWIND [
  [17, 33],
  [17, 183],
  [33, 183],
  [36, 65],
  [36, 198],
  [65, 198],
  [27, 81],
  [27, 307],
  [81, 307],
  [53, 58],
  [58, 187],
  [10, 18],
  [10, 346]
] AS pair
MATCH (source:User {userId: pair[0]}), (target:User {userId: pair[1]})
CALL gds.shortestPath.dijkstra.stream(
  'userGraph',
  {
    sourceNode: source,
    targetNode: target,
    relationshipWeightProperty: 'distance'
  }
)
YIELD totalCost, nodeIds
WITH
  pair,
  totalCost,
  size(nodeIds) - 1 AS hopCount,
  [nodeId IN nodeIds | gds.util.asNode(nodeId).userId] AS pathUsers
RETURN
  pair[0] AS sourceUserId,
  pair[1] AS targetUserId,
  hopCount,
  round(totalCost * 10000.0) / 10000.0 AS totalDistance,
  pathUsers
ORDER BY hopCount, totalDistance;

UNWIND [
  [17, 33],
  [17, 183],
  [33, 183],
  [36, 65],
  [36, 198],
  [65, 198],
  [27, 81],
  [27, 307],
  [81, 307],
  [53, 58],
  [58, 187],
  [10, 18],
  [10, 346]
] AS pair
MATCH (source:User {userId: pair[0]}), (target:User {userId: pair[1]})
CALL gds.shortestPath.dijkstra.stream(
  'userGraph',
  {
    sourceNode: source,
    targetNode: target,
    relationshipWeightProperty: 'distance'
  }
)
YIELD totalCost, nodeIds
WITH
  size(nodeIds) - 1 AS hopCount,
  totalCost
RETURN
  count(*) AS connectedPairs,
  round(avg(hopCount) * 100.0) / 100.0 AS avgHopCount,
  min(hopCount) AS minHopCount,
  max(hopCount) AS maxHopCount,
  round(avg(totalCost) * 10000.0) / 10000.0 AS avgDistance;

CALL gds.graph.drop('userGraph') YIELD graphName
RETURN 'Dropped projection' AS action, graphName;

MATCH ()-[sim:SIMILAR]-()
DELETE sim;
