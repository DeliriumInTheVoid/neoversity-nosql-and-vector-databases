// Query 1
// Top nodes by total degree across the whole graph
MATCH (n)
WITH n, count { (n)--() } AS degree
RETURN
  labels(n) AS labels,
  CASE
    WHEN n:User THEN "User " + toString(n.userId)
    WHEN n:Movie THEN "Movie " + toString(n.movieId) + ": " + n.title
    WHEN n:Genre THEN "Genre " + n.name
    ELSE toString(id(n))
  END AS node,
  degree
ORDER BY degree DESC
LIMIT 25;

// Query 2
// Degree distribution by node label
MATCH (n)
WITH labels(n)[0] AS label, count { (n)--() } AS degree
RETURN
  label,
  count(*) AS nodeCount,
  min(degree) AS minDegree,
  round(avg(degree) * 100.0) / 100.0 AS avgDegree,
  percentileCont(degree, 0.5) AS medianDegree,
  percentileCont(degree, 0.95) AS p95Degree,
  percentileCont(degree, 0.99) AS p99Degree,
  max(degree) AS maxDegree
ORDER BY maxDegree DESC;

// Query 3
// Most active users by number of RATED relationships
MATCH (u:User)
WITH u, count { (u)-[:RATED]->(:Movie) } AS ratingsGiven
RETURN
  u.userId AS userId,
  u.gender AS gender,
  u.age AS age,
  u.occupation AS occupation,
  ratingsGiven
ORDER BY ratingsGiven DESC
LIMIT 10;

// Query 4
// Most rated movies. These are supernodes on the Movie side
MATCH (m:Movie)
WITH
  m,
  count { (:User)-[:RATED]->(m) } AS ratingsReceived,
  count { (m)-[:HAS_GENRE]->(:Genre) } AS genreLinks,
  count { (m)--() } AS totalDegree
RETURN
  m.movieId AS movieId,
  m.title AS title,
  m.year AS year,
  ratingsReceived,
  genreLinks,
  totalDegree
ORDER BY totalDegree DESC
LIMIT 10;

// Query 5
// Genre nodes by fan-out to movies and implicit fan-out to ratings
MATCH (g:Genre)<-[:HAS_GENRE]-(m:Movie)
OPTIONAL MATCH (m)<-[r:RATED]-(:User)
WITH
  g,
  count(DISTINCT m) AS movieLinks,
  count(r) AS reachableRatings
RETURN
  g.name AS genre,
  movieLinks,
  reachableRatings
ORDER BY movieLinks DESC, reachableRatings DESC;

// Query 6
// Compare expansion cost for a supernode movie and a typical low-degree movie
MATCH (popular:Movie)
WITH popular, count { (:User)-[:RATED]->(popular) } AS popularRatings
ORDER BY popularRatings DESC
LIMIT 1
MATCH (typical:Movie)
WITH popular, popularRatings, typical, count { (:User)-[:RATED]->(typical) } AS typicalRatings
WHERE typicalRatings >= 20
WITH popular, popularRatings, typical, typicalRatings
ORDER BY abs(typicalRatings - 20), typical.movieId
LIMIT 1
RETURN
  popular.movieId AS popularMovieId,
  popular.title AS popularMovie,
  popularRatings,
  typical.movieId AS typicalMovieId,
  typical.title AS typicalMovie,
  typicalRatings,
  popularRatings - typicalRatings AS extraRelationshipsToScan;
