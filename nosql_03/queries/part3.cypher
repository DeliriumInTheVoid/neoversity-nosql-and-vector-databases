// Query 1
// Find Thriller movies with average rating above 4.0
MATCH (m:Movie)-[:HAS_GENRE]->(:Genre {name: "Thriller"})
MATCH (m)<-[r:RATED]-(:User)
WITH m, avg(r.rating) AS avgRating, count(r) AS ratingCount
WHERE avgRating > 4.0
RETURN
  m.movieId AS movieId,
  m.title AS title,
  m.year AS year,
  round(avgRating * 100.0) / 100.0 AS avgRating,
  ratingCount
ORDER BY avgRating DESC, ratingCount DESC, title
LIMIT 25;

// Query 2
// Find users who gave rating 5 to more than 50 movies
MATCH (u:User)-[r:RATED]->(:Movie)
WHERE r.rating = 5
WITH u, count(r) AS fiveStarRatings
WHERE fiveStarRatings > 50
RETURN
  u.userId AS userId,
  u.gender AS gender,
  u.age AS age,
  u.occupation AS occupation,
  u.zipCode AS zipCode,
  fiveStarRatings
ORDER BY fiveStarRatings DESC, userId
LIMIT 50;

// Query 3
// Find movies that both userId=1 and userId=2 rated highly
MATCH (u1:User {userId: 1})-[r1:RATED]->(m:Movie)<-[r2:RATED]-(u2:User {userId: 2})
WHERE r1.rating >= 4 AND r2.rating >= 4
RETURN
  m.movieId AS movieId,
  m.title AS title,
  m.year AS year,
  r1.rating AS user1Rating,
  r2.rating AS user2Rating
ORDER BY title;

// Query 4
// Find genres with consistently high ratings: average rating plus rating count
MATCH (g:Genre)<-[:HAS_GENRE]-(m:Movie)<-[r:RATED]-(:User)
WITH
  g,
  count(DISTINCT m) AS movieCount,
  count(r) AS ratingCount,
  avg(r.rating) AS avgRating,
  stDev(r.rating) AS ratingStdDev
WHERE ratingCount >= 1000 AND avgRating >= 3.5
RETURN
  g.name AS genre,
  movieCount,
  ratingCount,
  round(avgRating * 100.0) / 100.0 AS avgRating,
  round(ratingStdDev * 100.0) / 100.0 AS ratingStdDev
ORDER BY avgRating DESC, ratingCount DESC;

// Query 5
// Recommendation: users with similar taste also liked these movies
MATCH (target:User {userId: 1})-[targetRating:RATED]->(liked:Movie)
WHERE targetRating.rating >= 4
MATCH (similar:User)-[similarLiked:RATED]->(liked)
WHERE similar <> target AND similarLiked.rating >= 4
WITH target, similar, count(DISTINCT liked) AS sharedLikedMovies
WHERE sharedLikedMovies >= 3
WITH target, similar, sharedLikedMovies
ORDER BY sharedLikedMovies DESC
LIMIT 200
MATCH (similar)-[candidateRating:RATED]->(candidate:Movie)
WHERE candidateRating.rating >= 4
  AND NOT EXISTS {
    MATCH (target)-[:RATED]->(candidate)
  }
WITH
  candidate,
  count(DISTINCT similar) AS recommendingUsers,
  sum(sharedLikedMovies) AS similarityScore,
  avg(candidateRating.rating) AS avgRatingFromSimilarUsers
WHERE recommendingUsers >= 2
RETURN
  candidate.movieId AS movieId,
  candidate.title AS title,
  candidate.year AS year,
  recommendingUsers,
  similarityScore,
  round(avgRatingFromSimilarUsers * 100.0) / 100.0 AS avgRatingFromSimilarUsers
ORDER BY similarityScore DESC, avgRatingFromSimilarUsers DESC, recommendingUsers DESC, title
LIMIT 20;

// Query 6
// Find the shortest connection chain between two users through rated movies
MATCH (u1:User {userId: 1}), (u2:User {userId: 2})
MATCH p = shortestPath((u1)-[:RATED*..6]-(u2))
RETURN
  length(p) AS pathLength,
  [node IN nodes(p) |
    CASE
      WHEN node:User THEN "User " + toString(node.userId)
      WHEN node:Movie THEN "Movie " + toString(node.movieId) + ": " + node.title
      ELSE labels(node)[0]
    END
  ] AS pathNodes,
  [rel IN relationships(p) | type(rel) + " rating=" + toString(rel.rating)] AS pathRelationships;
