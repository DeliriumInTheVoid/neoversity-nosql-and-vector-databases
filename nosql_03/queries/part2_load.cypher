// 0 Lookup constraints
// Unique constraints also create backing indexes
CREATE CONSTRAINT user_id_unique IF NOT EXISTS
FOR (u:User) REQUIRE u.userId IS UNIQUE;

CREATE CONSTRAINT movie_id_unique IF NOT EXISTS
FOR (m:Movie) REQUIRE m.movieId IS UNIQUE;

CREATE CONSTRAINT genre_name_unique IF NOT EXISTS
FOR (g:Genre) REQUIRE g.name IS UNIQUE;

CREATE INDEX movie_year_index IF NOT EXISTS
FOR (m:Movie) ON (m.year);

// 1. Users
LOAD CSV WITH HEADERS FROM 'file:///users.csv' AS row
MERGE (u:User {userId: toInteger(row.userId)})
SET
  u.gender = row.gender,
  u.age = toInteger(row.age),
  u.occupation = toInteger(row.occupation),
  u.zipCode = row.zipCode;

// 2. Movies
LOAD CSV WITH HEADERS FROM 'file:///movies.csv' AS row
WITH
  row,
  CASE
    WHEN row.title =~ '.*\\([0-9]{4}\\)$'
    THEN trim(substring(row.title, 0, size(row.title) - 7))
    ELSE row.title
  END AS cleanTitle,
  CASE
    WHEN row.title =~ '.*\\([0-9]{4}\\)$'
    THEN toInteger(substring(row.title, size(row.title) - 5, 4))
    ELSE null
  END AS releaseYear
MERGE (m:Movie {movieId: toInteger(row.movieId)})
SET
  m.title = cleanTitle,
  m.year = releaseYear;

// 3. Genres
LOAD CSV WITH HEADERS FROM 'file:///movies.csv' AS row
WITH split(row.genres, '|') AS genres
UNWIND genres AS genreName
WITH DISTINCT trim(genreName) AS genreName
WHERE genreName <> ''
MERGE (:Genre {name: genreName});

// Wait until indexes are online before relationship loading starts
CALL db.awaitIndexes();

// 4. Movie-genre relationships
LOAD CSV WITH HEADERS FROM 'file:///movies.csv' AS row
MATCH (m:Movie {movieId: toInteger(row.movieId)})
WITH m, split(row.genres, '|') AS genres
UNWIND genres AS genreName
WITH m, trim(genreName) AS genreName
WHERE genreName <> ''
MATCH (g:Genre {name: genreName})
MERGE (m)-[:HAS_GENRE]->(g);

// 5. Rating relationships. Use batches because ratings.csv has 1,000,209 rows
CALL apoc.periodic.iterate(
  "LOAD CSV WITH HEADERS FROM 'file:///ratings.csv' AS row RETURN row",
  "
  MATCH (u:User {userId: toInteger(row.userId)})
  MATCH (m:Movie {movieId: toInteger(row.movieId)})
  MERGE (u)-[r:RATED]->(m)
  SET
    r.rating = toInteger(row.rating),
    r.timestamp = toInteger(row.timestamp)
  ",
  {
    batchSize: 10000,
    parallel: false
  }
);

// 6. Verification queries
MATCH (u:User) RETURN count(u) AS users;
MATCH (m:Movie) RETURN count(m) AS movies;
MATCH (g:Genre) RETURN count(g) AS genres;
MATCH (:Movie)-[r:HAS_GENRE]->(:Genre) RETURN count(r) AS movieGenreRelationships;
MATCH ()-[r:RATED]->() RETURN count(r) AS ratings;
