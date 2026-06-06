# Частина 1 — проєктування схеми

MovieLens 1M містить три основні типи даних:

- `users.dat`: користувачі та демографія.
- `movies.dat`: фільми та жанри.
- `ratings.dat`: оцінки користувачів для фільмів.

## ASCII-діаграма

```text
(:User)
  userId
  gender
  age
  occupation
  zipCode
    |
    |  RATED
    |  rating
    |  timestamp
    v
(:Movie) -----------------> (:Genre)
  movieId       HAS_GENRE     name
  title
  year
```

## Вузли

### `User`

```text
(:User {
  userId,
  gender,
  age,
  occupation,
  zipCode
})
```

`User` є вузлом, тому користувач бере участь у великій кількості зв'язків з фільмами через оцінки. Це центральна сутність для рекомендацій. Від користувача зручно йти до оцінених фільмів, схожих користувачів і жанрових уподобань.

Властивості:

- `userId`: унікальний ідентифікатор користувача з MovieLens.
- `gender`: стать користувача.
- `age`: код вікової групи.
- `occupation`: код професії.
- `zipCode`: поштовий індекс.

Демографічні поля залишаються властивостями `User`, а не окремими вузлами, бо в базовій моделі це одноцінні атрибути. Якщо надалі потрібно будувати багато запитів навколо професій або вікових груп, можна винести `Occupation` чи `AgeGroup` в окремі вузли.

### `Movie`

```text
(:Movie {
  movieId,
  title,
  year
})
```

`Movie` є вузлом, тому фільм має багато вхідних оцінок від користувачів і кілька зв'язків з жанрами. Фільм також є основною ціллю рекомендацій.

Властивості:

- `movieId`: унікальний ідентифікатор фільму з MovieLens.
- `title`: назва фільму без року.
- `year`: рік випуску, виділений з назви.

Рік зручно зберігати окремо, бо це дає прості запити на фільми певного періоду, наприклад `year >= 1990 AND year < 2000`.

### `Genre`

```text
(:Genre {
  name
})
```

`Genre` є вузлом, тому жанр повторюється у багатьох фільмах і природно утворює спільні групи. Це дозволяє швидко переходити від жанру до всіх його фільмів або від фільму до споріднених фільмів через спільні жанри.

Властивості:

- `name`: назва жанру, наприклад `Comedy`, `Action`, `Film-Noir`, `Children's`.

## Ребра

### `(User)-[:RATED]->(Movie)`

```text
(:User)-[:RATED {
  rating,
  timestamp
}]->(:Movie)
```

Напрямок: від користувача до фільму.

`RATED` є ребром, бо оцінка описує дію користувача щодо конкретного фільму. Вона не існує сама по собі без пари `User` і `Movie`.

Властивості:
- `rating`: оцінка від 1 до 5.
- `timestamp`: Unix-таймстемп моменту оцінювання.

Такий напрямок робить типові запити прямими:
- знайти всі фільми, які оцінив користувач;
- знайти рейтинг конкретного користувача для конкретного фільму;
- знайти користувачів, які оцінили той самий фільм;
- рахувати середню оцінку фільму через вхідні `RATED`.

### `(Movie)-[:HAS_GENRE]->(Genre)`

```text
(:Movie)-[:HAS_GENRE]->(:Genre)
```

Напрямок: від фільму до жанру.

`HAS_GENRE` не має обов'язкових властивостей. Воно просто фіксує належність фільму до одного або кількох жанрів.

Такий напрямок читається як "фільм має жанр". У Neo4j напрямок не заважає виконувати зворотні обходи, тому запити від жанру до фільмів також залишаються простими.

## Відповіді на обов'язкові питання

### 1. Які сутності стали вузлами, а які - ребрами? Чому?

Вузлами стали:
- `User`: самостійна сутність, яка має демографічні властивості та багато оцінок.
- `Movie`: самостійна сутність, яку оцінюють користувачі та яка належить до жанрів.
- `Genre`: повторювана категорія, що об'єднує багато фільмів.

Ребрами стали:
- `RATED`: дія користувача щодо фільму. Це зв'язок між двома сутностями, а не самостійний об'єкт у базовій моделі.
- `HAS_GENRE`: належність фільму до жанру. Це зв'язок між фільмом і категорією.

Логіка така: вузлами стають сутності, до яких потрібно часто звертатись напряму, групувати їх або будувати від них обхід графа. Ребрами стають відношення між сутностями, особливо якщо це відношення саме по собі найкраще описується як зв'язок.

### 2. Оцінка користувача за фільм: ребро `RATED` чи окремий вузол `Rating`?

У цій моделі оцінка є ребром:

```text
(:User)-[:RATED {rating, timestamp}]->(:Movie)
```

Причини:
- У MovieLens 1M оцінка завжди належить конкретній парі `User` і `Movie`.
- Оцінка має лише прості атрибути: значення `rating` і `timestamp`.
- Основні запити рекомендаційної системи потребують швидкого переходу `User -> Movie` або `Movie -> User`.
- Модель з ребром компактніша. Для 1 000 209 оцінок не потрібно створювати 1 000 209 додаткових вузлів.
- У Neo4j властивості ребра добре підходять для таких даних, як вага, дата або тип взаємодії.

Trade-off:
Модель з окремим вузлом `Rating` теж має сенс у складніших сценаріях:

```text
(:User)-[:CREATED]->(:Rating {rating, timestamp})-[:FOR_MOVIE]->(:Movie)
```

Переваги `Rating` як вузла:
- можна додавати до оцінки коментар, джерело, пристрій, сесію, експериментальну групу;
- можна зберігати історію змін оцінки;
- можна мати кілька оцінок одного користувача для одного фільму в різний час;
- можна зв'язувати оцінку з іншими сутностями, наприклад `Review`, `Session`, `RecommendationRun`.

Недоліки `Rating` як вузла:
- більше вузлів і ребер;
- складніші запити;
- довші обходи графа;
- більше місця в базі.

Для MovieLens 1M базова модель з `RATED` як ребром є кращою, бо дані прості, оцінка унікальна для пари користувач-фільм, а головні запити виграють від прямого зв'язку.

### 3. Чому жанри вигідніше зберігати як окремі вузли `Genre`, а не як список у властивості `Movie`?

Жанри краще моделювати окремими вузлами:

```text
(:Movie)-[:HAS_GENRE]->(:Genre)
```

Причини:
- Жанр є повторюваною сутністю. Один жанр має багато фільмів.
- Запити на фільми певного жанру стають графовими обходами, а не пошуком у списку рядків.
- Легко знаходити фільми зі спільними жанрами.
- Легко рахувати статистику за жанром. Наприклад кількість фільмів, середній рейтинг, популярність серед груп користувачів.
- Зменшується дублювання рядків і ризик різного написання одного жанру.
- Можна додати властивості жанру або зв'язки між жанрами без зміни моделі `Movie`.

Якщо зберігати жанри як список у `Movie.genres`, модель буде простішою для імпорту, але слабшою для графових запитів. Наприклад, пошук "усі фільми жанру Comedy" або "рекомендувати фільми зі схожими жанрами" буде менш природним і гірше масштабуватиметься.

## Обмеження та індекси

Для стабільного імпорту і швидких пошуків варто створити такі обмеження:

```cypher
CREATE CONSTRAINT user_id_unique IF NOT EXISTS
FOR (u:User) REQUIRE u.userId IS UNIQUE;

CREATE CONSTRAINT movie_id_unique IF NOT EXISTS
FOR (m:Movie) REQUIRE m.movieId IS UNIQUE;

CREATE CONSTRAINT genre_name_unique IF NOT EXISTS
FOR (g:Genre) REQUIRE g.name IS UNIQUE;
```

Ці обмеження гарантують, що імпорт не створить дублікати користувачів, фільмів або жанрів.

# Частина 2: завантаження даних

Запити для завантаження:

```text
queries/part2_load.cypher
```

CSV-файли у директорії `nosql_03/import` і вона змонтована в контейнер як `/var/lib/neo4j/import`. Тому в Cypher використовуються шляхи:

```text
file:///users.csv
file:///movies.csv
file:///ratings.csv
```

## Як запустити

З директорії `nosql_03`:

```powershell
docker cp .\queries\part2_load.cypher neo4j_movielens:/tmp/part2_load.cypher
docker exec neo4j_movielens cypher-shell -u neo4j -p password123 -f /tmp/part2_load.cypher
```

# Частина 3: запити різної складності

Запити у файлі:

```text
queries/part3.cypher
```

Запуск:

```powershell
docker cp .\queries\part3.cypher neo4j_movielens:/tmp/part3.cypher
docker exec neo4j_movielens cypher-shell -u neo4j -p password123 -f /tmp/part3.cypher
```

## Запит 1. Фільми жанру `Thriller` із середнім рейтингом вище `4.0`

```cypher
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
```

Що робить запит:
- знаходить вузол жанру `Thriller`;
- переходить до всіх фільмів цього жанру через `HAS_GENRE`;
- збирає всі вхідні ребра `RATED`;
- рахує середній рейтинг і кількість оцінок для кожного фільму;
- залишає тільки фільми із середнім рейтингом вище `4.0`.

Чому написано саме так:
- жанр шукається як вузол `Genre`, а не як текст у властивості фільму;
- `avg(r.rating)` працює напряму з властивістю ребра `RATED`;
- `count(r)` додано, щоб бачити надійність середнього рейтингу;
- `LIMIT 25` обмежує вивід, щоб повний запуск файлу не створював зайвий великий результат.

## Запит 2. Користувачі, які поставили `5` більш ніж 50 фільмам

```cypher
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
```

Що робить запит:
- обходить усі оцінки користувачів;
- залишає тільки оцінки зі значенням `5`;
- групує результат за користувачем;
- повертає користувачів, у яких більше ніж 50 максимальних оцінок.

Чому написано саме так:
- фільтр `WHERE r.rating = 5` застосовується до ребра, бо оцінка збережена як властивість `RATED`;
- `count(r)` рахує саме кількість п'ятизіркових оцінок;
- демографічні властивості повертаються разом із `userId`, щоб результат було зручніше аналізувати.

## Запит 3. Фільми, які два користувачі високо оцінили

```cypher
MATCH (u1:User {userId: 1})-[r1:RATED]->(m:Movie)<-[r2:RATED]-(u2:User {userId: 2})
WHERE r1.rating >= 4 AND r2.rating >= 4
RETURN
  m.movieId AS movieId,
  m.title AS title,
  m.year AS year,
  r1.rating AS user1Rating,
  r2.rating AS user2Rating
ORDER BY title;
```

Що робить запит:
- бере користувачів `userId=1` і `userId=2`;
- шукає фільми, до яких ведуть ребра `RATED` від обох користувачів;
- залишає тільки ті фільми, де обидві оцінки не нижчі за `4`.

Чому написано саме так:
- конструкція `(u1)-[:RATED]->(m)<-[:RATED]-(u2)` напряму описує спільно оцінений фільм;
- фільтр `rating >= 4` означає "високо оцінили", але не вимагає максимальної оцінки `5`;
- повертаються обидві оцінки, щоб було видно, наскільки смаки збігаються.

## Запит 4. Жанри зі стабільно високими оцінками

```cypher
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
```

Що робить запит:
- проходить від жанру до фільмів і далі до оцінок;
- для кожного жанру рахує кількість фільмів, кількість оцінок, середній рейтинг і стандартне відхилення;
- залишає жанри з достатньою кількістю оцінок і середнім рейтингом не нижче `3.5`.

Чому написано саме так:
- `ratingCount >= 1000` відсікає жанри з надто малою вибіркою;
- `avgRating >= 3.5` задає поріг "високих" оцінок на рівні жанру;
- `stDev(r.rating)` показує стабільність: нижче стандартне відхилення означає, що оцінки менш розкидані;
- `count(DISTINCT m)` потрібен, бо один жанр має багато фільмів і кожен фільм має багато оцінок.

## Запит 5. Рекомендація "користувачі зі схожими смаками також дивилися"

```cypher
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
```

Що робить запит:
- бере цільового користувача `userId=1`;
- знаходить фільми, які він оцінив високо (`rating >= 4`);
- знаходить інших користувачів, які теж високо оцінили ці самі фільми;
- залишає схожих користувачів, які мають щонайменше 3 спільні високо оцінені фільми;
- бере фільми, які схожі користувачі високо оцінили, але цільовий користувач ще не оцінював;
- ранжує рекомендації за кількістю схожих користувачів і силою схожості.

Чому написано саме так:
- схожість визначається через спільні high-rating фільми, а не через усі переглянуті фільми;
- `sharedLikedMovies >= 3` зменшує шум від випадкового збігу одного фільму;
- `LIMIT 200` обмежує кількість схожих користувачів, щоб запит був практичним на 1M оцінок;
- `NOT EXISTS { MATCH (target)-[:RATED]->(candidate) }` гарантує, що не рекомендуються вже оцінені фільми;
- `similarityScore` підсилює кандидатів, яких рекомендують користувачі з більшою кількістю спільних вподобань.

## Запит 6. Найкоротший ланцюжок між двома користувачами

```cypher
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
```

Що робить запит:
- бере двох користувачів `userId=1` і `userId=2`;
- шукає найкоротший шлях між ними через ребра `RATED`;
- дозволяє шлях довжиною до 6 ребер;
- повертає довжину шляху, вузли шляху і оцінки на ребрах.

Чому написано саме так:
- використано `shortestPath`, бо потрібно знайти мінімальний ланцюжок зв'язку, а не всі можливі ланцюжки;
- ребро `RATED` обходиться без напрямку `-[:RATED]-`, бо для зв'язності важливо, що користувач і фільм пов'язані оцінкою, а не напрямок зберігання;
- обмеження `*..6` захищає від надто широкого обходу великого графа.

## Інтерпретація довжини шляху

Довжина шляху в Neo4j означає кількість ребер у цьому шляху.

У цій моделі один хоп - це один перехід по ребру `RATED` між користувачем і фільмом. Граф для `RATED` є двочастковим, тобто ребра йдуть тільки між `User` і `Movie`, а не напряму між двома користувачами або двома фільмами.

Шлях довжини `2`:

```text
(:User)-[:RATED]->(:Movie)<-[:RATED]-(:User)
```

Це означає, що два користувачі оцінили один і той самий фільм. Це найсильніший прямий зв'язок через спільний фільм.

Шлях довжини `4`:

```text
(:User)-[:RATED]->(:Movie)<-[:RATED]-(:User)-[:RATED]->(:Movie)<-[:RATED]-(:User)
```

Це означає, що між двома користувачами є один проміжний користувач і два фільми. Інтерпретація: перший користувач має спільний фільм з проміжним користувачем, а проміжний користувач має інший спільний фільм з другим користувачем.

Шлях довжини `6`:

```text
(:User)-[:RATED]->(:Movie)<-[:RATED]-(:User)-[:RATED]->(:Movie)<-[:RATED]-(:User)-[:RATED]->(:Movie)<-[:RATED]-(:User)
```

Це ще непрямий зв'язок. Між двома користувачами є два проміжні користувачі і три фільми. Такий шлях показує слабший зв'язок смаків, бо користувачі пов'язані не одним спільним фільмом, а ланцюжком спільних оцінок через інших користувачів.

Для шляхів між двома користувачами довжини зазвичай парні: `2`, `4`, `6`. Це наслідок двочасткової структури графа `User-Movie`.

# Частина 4: виявлення супервузлів

Усі запити у файлі:

```text
queries/part4_supernodes.cypher
```

Запуск:

```powershell
docker cp .\queries\part4_supernodes.cypher neo4j_movielens:/tmp/part4_supernodes.cypher
docker exec neo4j_movielens cypher-shell -u neo4j -p password123 -f /tmp/part4_supernodes.cypher
```

## Що таке супервузол у цьому графі

Супервузол - це вузол з аномально великою кількістю ребер порівняно з іншими вузлами того самого типу або порівняно з типовим fan-out запиту.

У MovieLens це очікувано виникає у трьох місцях:
- популярні фільми, які отримали тисячі оцінок;
- дуже активні користувачі, які оцінили тисячі фільмів;
- жанри, які з'єднані з великою кількістю фільмів і через них ведуть до сотень тисяч оцінок.

## Запит 1. Top-degree вузли у всьому графі

```cypher
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
```

Що робить запит:
- проходить по всіх вузлах графа;
- рахує кількість інцидентних ребер для кожного вузла;
- повертає 25 вузлів з найбільшим degree.

Чому написано саме так:
- `count { (n)--() }` рахує всі ребра вузла незалежно від напрямку;
- напрямок тут не важливий, бо супервузол визначається кількістю зв'язків, а не тим, вхідні вони чи вихідні;
- `CASE` робить результат читабельним для різних типів вузлів.

Фактичний результат показав, що найбільші вузли за degree - це популярні фільми:

```text
American Beauty                         degree 3430
Star Wars: Episode IV - A New Hope      degree 2995
Star Wars: Episode V - The Empire...    degree 2995
Star Wars: Episode VI - Return...       degree 2888
Jurassic Park                           degree 2675
Saving Private Ryan                     degree 2656
Terminator 2: Judgment Day              degree 2652
Matrix, The                             degree 2593
Back to the Future                      degree 2585
Silence of the Lambs, The               degree 2580
```

## Запит 2. Розподіл degree за типами вузлів

```cypher
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
```

Що робить запит:
- групує вузли за лейблом;
- рахує мінімальний, середній, медіанний, 95-й і 99-й перцентилі degree;
- показує максимальний degree для кожного типу вузлів.

Чому написано саме так:
- саме порівняння з медіаною і перцентилями показує аномальність;
- просто знати `maxDegree` недостатньо, бо для різних лейблів нормальний degree різний;
- `p95Degree` і `p99Degree` дають практичний поріг для виявлення хвоста розподілу.

Фактичні результати:
```text
Movie: nodeCount 3883, avg 259.24, median 111, p99 1759.58, max 3430
User:  nodeCount 6040, avg 165.60, median 96,  p99 906.66,  max 2314
Genre: nodeCount 18,   avg 356.00, median 231, p99 1534.49, max 1603
```

Інтерпретація:
- `Movie` з degree понад `1759` вже у верхньому 1% за популярністю;
- `User` з degree понад `906` вже у верхньому 1% за активністю;
- `Genre` має лише 18 вузлів, тому навіть кілька жанрів можуть бути дуже великими відносно решти.

## Запит 3. Найактивніші користувачі

```cypher
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
```

Що робить запит:
- рахує кількість `RATED` ребер, які виходять від кожного користувача;
- повертає 10 найактивніших користувачів.

Чому написано саме так:
- для `User` важливий саме вихідний degree по `RATED`;
- демографічні поля повертаються для контексту;
- `LIMIT 10` достатній для виявлення верхнього хвоста.

Фактичні супервузли серед користувачів:

```text
User 4169: 2314 ratings
User 1680: 1850 ratings
User 4277: 1743 ratings
User 1941: 1595 ratings
User 1181: 1521 ratings
```

Ці користувачі значно перевищують медіану `96` оцінок на користувача.

## Запит 4. Найпопулярніші фільми

```cypher
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
```

Що робить запит:
- окремо рахує кількість оцінок фільму;
- окремо рахує кількість жанрових ребер;
- повертає загальний degree.

Чому написано саме так:
- для `Movie` основний внесок у супервузол дають вхідні `RATED`;
- `HAS_GENRE` ребер мало, але вони теж входять у загальний degree;
- розділення `ratingsReceived` і `genreLinks` пояснює, з чого складається degree.

Фактичні супервузли серед фільмів:

```text
American Beauty: 3428 ratings, 2 genres, totalDegree 3430
Star Wars: Episode IV - A New Hope: 2991 ratings, 4 genres, totalDegree 2995
Star Wars: Episode V - The Empire Strikes Back: 2990 ratings, 5 genres, totalDegree 2995
Star Wars: Episode VI - Return of the Jedi: 2883 ratings, 5 genres, totalDegree 2888
Jurassic Park: 2672 ratings, 3 genres, totalDegree 2675
```

Це найочевидніші супервузли графа: один популярний фільм має тисячі вхідних оцінок.

## Запит 5. Жанри як супервузли

```cypher
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
```

Що робить запит:
- рахує, скільки фільмів пов'язано з кожним жанром;
- рахує, скільки оцінок стає досяжними, якщо з жанру перейти до фільмів і далі до `RATED`.

Чому написано саме так:
- прямий degree жанру показує тільки кількість `HAS_GENRE`;
- реальна вартість запитів часто виникає на другому кроці, коли жанр розгортається у фільми, а фільми - в оцінки;
- `count(DISTINCT m)` потрібен, бо після `OPTIONAL MATCH` один фільм повторюється для кожної своєї оцінки.

Фактичні жанрові супервузли:

```text
Drama: 1603 movie links, 354529 reachable ratings
Comedy: 1200 movie links, 356580 reachable ratings
Action: 503 movie links, 257457 reachable ratings
Thriller: 492 movie links, 189680 reachable ratings
Romance: 471 movie links, 147523 reachable ratings
```

Так, жанрові вузли теж є супервузлами. `Drama` і `Comedy` особливо важливі: їхній прямий degree менший за degree найпопулярніших фільмів, але запит виду `Genre -> Movie -> RATED` одразу відкриває сотні тисяч ребер.

## Запит 6. Порівняння супервузла зі звичайним вузлом

```cypher
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
```

Що робить запит:
- знаходить найпопулярніший фільм;
- знаходить типовий малий фільм приблизно з 20 оцінками;
- показує різницю в кількості ребер, які треба просканувати при обході.

Фактичний результат:

```text
Popular movie: American Beauty, 3428 ratings
Typical movie: Colonel Chabert, Le, 20 ratings
Extra relationships to scan: 3408
```

Це демонструє проблему супервузлів: обидва фільми можуть бути знайдені через індекс за `movieId`, але після знаходження вузла обхід його ребер має зовсім різну вартість.

## Відповіді на обов'язкові питання

### 1. Які вузли виявилися супервузлами? Скільки у них зв'язків?

Супервузли серед фільмів:

```text
American Beauty: totalDegree 3430
Star Wars: Episode IV - A New Hope: totalDegree 2995
Star Wars: Episode V - The Empire Strikes Back: totalDegree 2995
Star Wars: Episode VI - Return of the Jedi: totalDegree 2888
Jurassic Park: totalDegree 2675
```

Супервузли серед користувачів:

```text
User 4169: 2314 ratings
User 1680: 1850 ratings
User 4277: 1743 ratings
User 1941: 1595 ratings
User 1181: 1521 ratings
```

Супервузли серед жанрів:

```text
Drama: 1603 movie links, 354529 reachable ratings
Comedy: 1200 movie links, 356580 reachable ratings
Action: 503 movie links, 257457 reachable ratings
Thriller: 492 movie links, 189680 reachable ratings
Romance: 471 movie links, 147523 reachable ratings
```

Найбільший прямий degree має `American Beauty`: `3430` зв'язків. Найбільший жанровий fan-out за оцінками має `Comedy`: `356580` досяжних оцінок через фільми жанру.

### 2. Чому запит, що зачіпає супервузол, працює повільніше, ніж запит по звичайному вузлу з тими самими індексами?

Індекс допомагає швидко знайти стартовий вузол, наприклад:

```cypher
MATCH (m:Movie {movieId: 2858})
```

Але індекс не прибирає потребу обходити ребра цього вузла.

Якщо після знаходження вузла запит робить:

```cypher
MATCH (m)<-[r:RATED]-(:User)
```

Neo4j має пройти по всіх відповідних ребрах `RATED`, які під'єднані до цього фільму.

Для `American Beauty` це `3428` оцінок. Для типового малого фільму з прикладу це лише `20` оцінок. Обидва вузли можна знайти через однаковий індекс, але після цього обсяг роботи відрізняється у понад 170 разів.

Тому проблема супервузла - це не пошук самого вузла, а вибух cardinality після його знаходження:
- більше ребер для сканування;
- більше проміжних рядків у query pipeline;
- дорожчі агрегації `avg`, `count`, `collect`;
- більше пам'яті для сортування і групування;
- більший ризик повільних multi-hop traversal.

Для жанру проблема ще сильніша. `Comedy` має `1200` прямі зв'язки з фільмами, але перехід `Comedy -> Movie -> RATED` розгортається до `356580` оцінок.

### 3. Яку конкретну стратегію застосувати для цього датасету?

Для цього датасету я б застосував стратегію bucketing, тобто розбиття супервузлів на проміжні вузли-бакети.

Найважливіший кандидат - жанри. `Genre` потрібен як логічна сутність, але `Drama` і `Comedy` мають великий fan-out. Якщо часто виконувати запити від жанру до фільмів і рейтингів, варто не стартувати з одного великого вузла `(:Genre {name: "Comedy"})`.

Практична схема:

```text
(:Genre {name})
    |
    | HAS_BUCKET
    v
(:GenreBucket {genre, decade})
    ^
    | IN_GENRE_BUCKET
(:Movie {movieId, title, year})
```

Приклад бакетів:

```text
GenreBucket {genre: "Comedy", decade: 1980}
GenreBucket {genre: "Comedy", decade: 1990}
GenreBucket {genre: "Drama", decade: 1990}
```

Що це дає:
- запит `Comedy movies from the 1990s` не обходить усі 1200 comedy-фільмів;
- fan-out розбивається на менші частини;
- рекомендаційні та аналітичні запити можуть стартувати з більш селективного бакета;
- сам вузол `Genre` можна залишити для навігації, опису жанру і загальних агрегатів.

Для глобальної статистики жанрів варто також зберігати попередньо обчислені агрегати:

```text
Genre.movieCount
Genre.ratingCount
Genre.avgRating
```

або окремі вузли:

```text
(:GenreStats {genre, ratingCount, avgRating, updatedAt})
```

Це краще, ніж щоразу виконувати дорогий обхід:

```text
Genre -> Movie -> RATED
```

Популярні фільми і дуже активні користувачі теж є супервузлами. Для них практичніша стратегія - починати запити з більш селективної сторони, додавати пороги і `LIMIT`, а важкі рекомендаційні агрегати рахувати окремими batch-процесами.

# Частина 5: графові алгоритми через GDS

Запити у файлі:

```text
queries/part5_gds.cypher
```

Запуск:

```powershell
docker cp .\queries\part5_gds.cypher neo4j_movielens:/tmp/part5_gds.cypher
docker exec neo4j_movielens cypher-shell -u neo4j -p password123 -f /tmp/part5_gds.cypher
```

У середовищі використано GDS `2.6.9`. Повний запуск зайняв приблизно 9 хвилин 19 секунд.

Після виконання скрипт видаляє GDS-проєкції та тимчасові ребра:

```text
CO_RATED = 0
SIMILAR = 0
```

Властивість `User.louvainCommunity` залишається в базі як результат Louvain. Повторний запуск скрипта перезаписує її.

## 5.1. PageRank на графі фільмів

### Крок 1. Матеріалізація `CO_RATED`

```cypher
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
```

Що робить запит:
- знаходить пари фільмів, які один і той самий користувач оцінив високо;
- `rating >= 4` означає позитивну оцінку;
- `id(m1) < id(m2)` прибирає дублікати пар;
- `weight = count(u)` показує, скільки користувачів високо оцінили обидва фільми;
- фільтрує фільми з дуже малою кількістю оцінок;
- залишає 50 000 найсильніших movie-movie зв'язків.

Чому написано саме так:
- GDS працює з проєкціями, а не напряму з implicit pattern `Movie <- User -> Movie`;
- PageRank потребує явних ребер між вузлами проєкції;
- вага ребра важлива. 500 спільних користувачів мають означати сильніший зв'язок, ніж 5.

### Крок 2. Проєкція `movieGraph`

```cypher
CALL gds.graph.project(
  'movieGraph',
  'Movie',
  { CO_RATED: { orientation: 'UNDIRECTED', properties: 'weight' } }
)
YIELD graphName, nodeCount, relationshipCount;
```

Що робить запит:
- створює in-memory GDS-граф `movieGraph`;
- вузли: `Movie`;
- ребра: `CO_RATED`;
- граф неорієнтований, бо co-rating симетричний;
- властивість `weight` передається в GDS.

Фактичний результат:

```text
movieGraph: 3883 nodes, 100000 relationships
```

У GDS неорієнтована проєкція з 50 000 збережених ребер відображається як 100 000 напрямлених adjacency entries.

### Крок 3. PageRank

```cypher
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
```

Що робить запит:
- запускає PageRank на графі фільмів;
- використовує `weight`, щоб сильніші co-rating зв'язки більше впливали на score;
- повертає не тільки PageRank, а й `ratingCount` та `avgRating` для інтерпретації.

Топ результатів:

```text
American Beauty: PageRank 9.65881, ratingCount 3428, avgRating 4.32
Star Wars: Episode IV: PageRank 9.13630, ratingCount 2991, avgRating 4.45
Star Wars: Episode V: PageRank 9.10046, ratingCount 2990, avgRating 4.29
Raiders of the Lost Ark: PageRank 7.93851, ratingCount 2514, avgRating 4.48
Fargo: PageRank 7.03170, ratingCount 2513, avgRating 4.25
```

### Відповідь: що означає високий PageRank для фільму?

Високий PageRank у цьому графі не означає просто "популярний фільм".

У цьому графі фільм отримує високий PageRank, якщо він:
- має сильні `CO_RATED` зв'язки з багатьма іншими фільмами;
- пов'язаний не просто з будь-якими фільмами, а з іншими центральними фільмами;
- часто входить у спільні high-rating патерни користувачів.

Популярність і PageRank тут корелюють, бо популярні фільми мають більше шансів мати багато co-rating зв'язків. Але PageRank додає структурний сенс: фільм є центральним у мережі смаків, якщо він з'єднує багато сильних high-rating сусідств.

Наприклад, `American Beauty`, `Star Wars`, `Raiders of the Lost Ark`, `Fargo` - це не просто фільми з багатьма оцінками. Це фільми, які часто з'являються разом з іншими високо оціненими фільмами у профілях користувачів.

## 5.2. Louvain для спільнот користувачів

### Крок 1. Матеріалізація `SIMILAR`

Повний варіант `rating >= 4` для user-user similarity перевищив ліміт транзакційної пам'яті. Тому застосовано дозволене в умові посилення порогу до `rating = 5` і додатковий фільтр проти pair explosion від надто популярних фільмів.

```cypher
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
```

Що робить запит:
- бере тільки максимальні оцінки `5`;
- використовує фільми, які мають від 20 до 500 п'ятизіркових оцінок;
- створює зв'язок між користувачами, якщо вони мають спільні 5-зіркові фільми;
- `weight` дорівнює кількості таких спільних фільмів;
- `distance = 1 / weight` потрібна для Dijkstra в секції 5.3.

Чому написано саме так:
- `rating = 5` дає чистіший сигнал схожості, ніж просто `rating >= 4`;
- фільми з тисячами п'ятірок створюють надто багато user-user пар і домінують граф;
- `weight >= 2` прибирає випадковий збіг по одному фільму;
- `LIMIT 30000` робить граф достатньо компактним для GDS у цьому контейнері.

### Крок 2. Проєкція `userSimilarity`

```cypher
CALL gds.graph.project(
  'userSimilarity',
  'User',
  { SIMILAR: { orientation: 'UNDIRECTED', properties: ['weight', 'distance'] } }
)
YIELD graphName, nodeCount, relationshipCount;
```

Фактичний результат:

```text
userSimilarity: 6040 nodes, 60000 relationships
```

Вузлів 6040, бо проєктуються всі користувачі. Частина з них ізольована, якщо не потрапила в top similarity edges.

### Крок 3. Louvain

```cypher
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
  nodePropertiesWritten;
```

Що робить запит:
- запускає Louvain на user-user similarity graph;
- використовує `weight`, щоб сильніші зв'язки більше впливали на спільноти;
- записує номер спільноти у `User.louvainCommunity`.

Фактичний результат:

```text
communityCount: 4716
modularity: 0.1890
ranLevels: 2
nodePropertiesWritten: 6040
```

Інтерпретація:
- велика кількість спільнот пояснюється sparse projection, багато користувачів не потрапили в top-30000 similarity edges і стали singleton communities;
- modularity `0.189` означає помірну структуру спільнот, але не ідеально чисті кластери;
- це очікувано для MovieLens, бо популярні фільми створюють багато перетинів між смаками.

### Крок 4a. Розміри кластерів

```cypher
MATCH (u:User)
WHERE u.louvainCommunity IS NOT NULL
RETURN
  u.louvainCommunity AS communityId,
  count(u) AS userCount
ORDER BY userCount DESC
LIMIT 10;
```

Фактичні найбільші кластери:

```text
community 4276: 469 users
community 2908: 336 users
community 3066: 228 users
community 2029: 187 users
community 1634: 109 users
```

Решта top-10 у цьому запуску включає singleton communities. Це важлива ознака, граф схожості після фільтрації має кілька великих компонентів і багато ізольованих або слабко представлених користувачів.

### Крок 4b. Топ жанри для спільнот

```cypher
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
```

Що робить запит:
- бере 10 найбільших Louvain communities;
- для користувачів у кожній спільноті бере фільми з оцінкою `>= 4`;
- рахує жанри цих фільмів;
- повертає 3 найпопулярніші жанри на кластер.

Фактичні результати для великих кластерів:

```text
community 4276: Drama, Comedy, Action
community 2908: Comedy, Action, Drama
community 3066: Drama, Comedy, Action
community 2029: Drama, Comedy, Thriller
community 1634: Comedy, Drama, Romance
```

### Відповіді: чи відповідають кластери інтуїтивним групам?

Частково так.

Кластери не є ідеально чистими групами типу "тільки любителі бойовиків" або "тільки арт-хаус". MovieLens 1M має багато mainstream-фільмів, які подобаються різним групам, тому `Drama` і `Comedy` часто з'являються майже всюди.

Але відмінності видно:
- `community 2908`: сильний профіль `Comedy + Action`, тобто ближче до blockbuster/action-comedy смаків;
- `community 2029`: `Drama + Comedy + Thriller`, більше тяжіє до драм і трилерів;
- `community 1634`: `Comedy + Drama + Romance`, більш романтично-комедійний профіль;
- `community 4276` і `3066`: mainstream drama-heavy профілі.

### Як це перевірено?

Перевірка зроблена через жанрові профілі кластерів:
1. Louvain записав `louvainCommunity` для кожного користувача.
2. Для кожної великої спільноти взято фільми, які її користувачі оцінили `>= 4`.
3. Через `HAS_GENRE` пораховано найчастіші жанри.
4. Топ-3 жанри порівняні між кластерами.

Це практичний спосіб інтерпретувати community detection: сам номер community не має змісту, зміст з'являється після аналізу поведінки користувачів усередині кластеру.

## 5.3. Dijkstra: найкоротший шлях між користувачами

Для Dijkstra використовується та сама user-user модель, що і для Louvain, але важливо не використовувати `weight` як відстань.

`SIMILAR.weight` означає силу схожості:

```text
більше weight = більше спільних 5-зіркових фільмів = ближчі користувачі
```

Dijkstra мінімізує суму ваг. Тому для shortest path використано:

```text
SIMILAR.distance = 1.0 / weight
```

Тоді сильніша схожість має меншу вартість переходу.

### Обрана пара користувачів

```cypher
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
```

Фактичний результат:

```text
sourceUserId: 36
targetUserId: 65
hopCount: 3
intermediateUsers: 2
totalDistance: 0.0806
pathUsers: [36, 4277, 3032, 65]
```

Інтерпретація:
- між користувачами 36 і 65 немає найсильнішого прямого similarity-зв'язку;
- найкоротший шлях проходить через двох проміжних користувачів: 4277 і 3032;
- у user-user similarity graph один hop означає один зв'язок `SIMILAR`, тобто спільні 5-зіркові фільми між двома користувачами.

### Кілька пар і середня довжина шляху

Для перевірки використано 13 пар користувачів із великих компонентів similarity graph:

```text
[17,33], [17,183], [33,183], [36,65], [36,198],
[65,198], [27,81], [27,307], [81,307], [53,58],
[58,187], [10,18], [10,346]
```

Фактичний результат:

```text
connectedPairs: 13
avgHopCount: 2.0
minHopCount: 1
maxHopCount: 3
avgDistance: 0.0648
```

Приклади шляхів:

```text
53 -> 58: hopCount 1
10 -> 346: hopCount 1
58 -> 4277 -> 187: hopCount 2
36 -> 4277 -> 3032 -> 65: hopCount 3
27 -> 4169 -> 5100 -> 81: hopCount 3
```

### Відповідь: наскільки "тісний світ" у цьому датасеті?

У найбільших зв'язаних компонентах similarity graph світ досить тісний. Для перевірених пар середня довжина шляху дорівнює `2.0`, а максимум серед вибірки - `3` hops.

Але це твердження не можна автоматично поширювати на всіх 6040 користувачів. Через фільтрацію до top-30000 `SIMILAR` ребер і поріг `rating = 5` багато користувачів залишаються ізольованими або потрапляють у singleton communities. Це видно з Louvain: `4716` communities, багато з них мають розмір 1.

Отже:
- всередині великих компонентів користувачі справді близькі;
- глобально граф не є повністю зв'язним;
- для ізольованих користувачів shortest path у цій проєкції не існує.

### Відповідь: яка середня довжина шляху і чи підтверджується "шість рукостискань"?

Для вибірки з 13 з'єднаних пар:

```text
avgHopCount = 2.0
minHopCount = 1
maxHopCount = 3
```

У межах цієї зв'язної частини графа гіпотеза "шести рукостискань" підтверджується, всі перевірені пари мають шлях коротший за 6 hops.

Але для всього датасету ситуація інша. У пруненій GDS-проєкції є ізольовані користувачі, тому не кожна пара користувачів має шлях. Тобто "шість рукостискань" підтверджується для з'єднаних компонентів, але не для всіх можливих пар користувачів у sparse similarity graph.

# Частина 6: аналіз і висновки

## 1. Граф vs SQL

Базові запити з частини 3 можна написати і в SQL без особливих проблем. Наприклад, "фільми жанру Thriller із середнім рейтингом вище 4.0" у реляційній моделі `movies`, `genres`, `movie_genres`, `ratings` виглядав би як звичайний набір `JOIN`, `GROUP BY` і `HAVING`. Для таких запитів SQL навіть дуже природний, бо вони табличні: взяти набір рядків, згрупувати, порахувати агрегати, відсортувати. Наприклад:

```sql
SELECT
  m.movie_id,
  m.title,
  m.year,
  AVG(r.rating) AS avg_rating,
  COUNT(*) AS rating_count
FROM movies AS m
JOIN movie_genres AS mg ON mg.movie_id = m.movie_id
JOIN genres AS g ON g.genre_id = mg.genre_id
JOIN ratings AS r ON r.movie_id = m.movie_id
WHERE g.name = 'Thriller'
GROUP BY m.movie_id, m.title, m.year
HAVING AVG(r.rating) > 4.0
ORDER BY avg_rating DESC, rating_count DESC;
```

Складність починається у запитах, де важлива не одна агрегація, а багаторазовий перехід по зв'язках. Запит 5 з частини 3 - рекомендація "користувачі зі схожими смаками також дивилися" - у Cypher читається майже як формулювання задачі, від цільового користувача перейти до високо оцінених фільмів, від них до схожих користувачів, далі до кандидатних фільмів, які цільовий користувач ще не оцінював. У SQL це перетворюється на кілька self-join до таблиці `ratings`, проміжну агрегацію схожих користувачів і ще один anti-join проти вже оцінених фільмів:

```sql
WITH target_likes AS (
  SELECT movie_id
  FROM ratings
  WHERE user_id = 1 AND rating >= 4
),
similar_users AS (
  SELECT
    r.user_id AS similar_user_id,
    COUNT(DISTINCT r.movie_id) AS shared_liked_movies
  FROM ratings AS r
  JOIN target_likes AS tl ON tl.movie_id = r.movie_id
  WHERE r.user_id <> 1
    AND r.rating >= 4
  GROUP BY r.user_id
  HAVING COUNT(DISTINCT r.movie_id) >= 3
  ORDER BY shared_liked_movies DESC
  LIMIT 200
),
candidates AS (
  SELECT
    r.movie_id,
    COUNT(DISTINCT su.similar_user_id) AS recommending_users,
    SUM(su.shared_liked_movies) AS similarity_score,
    AVG(r.rating) AS avg_rating_from_similar_users
  FROM similar_users AS su
  JOIN ratings AS r ON r.user_id = su.similar_user_id
  WHERE r.rating >= 4
    AND NOT EXISTS (
      SELECT 1
      FROM ratings AS already
      WHERE already.user_id = 1
        AND already.movie_id = r.movie_id
    )
  GROUP BY r.movie_id
  HAVING COUNT(DISTINCT su.similar_user_id) >= 2
)
SELECT
  m.movie_id,
  m.title,
  m.year,
  c.recommending_users,
  c.similarity_score,
  c.avg_rating_from_similar_users
FROM candidates AS c
JOIN movies AS m ON m.movie_id = c.movie_id
ORDER BY c.similarity_score DESC,
         c.avg_rating_from_similar_users DESC,
         c.recommending_users DESC,
         m.title
LIMIT 20;
```

Цей SQL-запит існує, але він менш прозорий. Фактична логіка графового обходу захована у self-join-ах до `ratings`. Також оптимізатору SQL потрібно будувати складний план для великих проміжних множин. У Neo4j модель явно зберігає зв'язки `(:User)-[:RATED]->(:Movie)`, тому запит краще відповідає предметній області: "йти по ребрах" замість "відновлювати ребра через join-таблицю".

Найскладніший приклад - запит 6 з частини 3, тобто найкоротший ланцюжок між користувачами через спільні фільми. У SQL без спеціального graph extension це можливо тільки через рекурсивний CTE, ручне обмеження глибини, масив visited-вузлів для захисту від циклів і додаткову логіку для вибору найкоротшого шляху. Приблизний PostgreSQL-варіант для user-movie graph міг би виглядати так:

```sql
WITH RECURSIVE graph_edges AS (
  SELECT
    'U' || user_id::text AS src,
    'M' || movie_id::text AS dst
  FROM ratings
  UNION ALL
  SELECT
    'M' || movie_id::text AS src,
    'U' || user_id::text AS dst
  FROM ratings
),
paths AS (
  SELECT
    src,
    dst,
    ARRAY[src, dst] AS path,
    1 AS depth
  FROM graph_edges
  WHERE src = 'U1'

  UNION ALL

  SELECT
    p.src,
    e.dst,
    p.path || e.dst,
    p.depth + 1
  FROM paths AS p
  JOIN graph_edges AS e ON e.src = p.dst
  WHERE p.depth < 6
    AND NOT e.dst = ANY(p.path)
)
SELECT path, depth
FROM paths
WHERE dst = 'U2'
ORDER BY depth
LIMIT 1;
```

Такий SQL технічно можливий, але він громіздкий, погано масштабується на dense graph і не є природним для задачі shortest path. У Cypher цей самий задум виражається напряму через `shortestPath((u1)-[:RATED*..6]-(u2))`. Ще більша різниця з'являється в частині 5: PageRank, Louvain і Dijkstra в SQL довелося б реалізовувати вручну або через окремі аналітичні бібліотеки, тоді як Neo4j GDS працює з графовою проєкцією напряму.

## 2. Де граф програє

Графова модель не є універсально кращою. Для багатьох задач MovieLens реляційна модель підійшла б простіше і дешевше. Наприклад, глобальні звіти "середній рейтинг по всіх фільмах", "кількість оцінок по місяцях", "топ професій за кількістю користувачів", "розподіл оцінок 1-5" природно лягають на SQL. Це табличні агрегації над великими наборами рядків, де `ratings` як fact table і `users`/`movies`/`genres` як dimension tables працюють дуже ефективно. Реляційні СУБД мають зрілі механізми для таких задач: columnar execution у деяких системах, materialized views, window functions, partitioning, статистику оптимізатора, BI-інтеграції та стабільний експорт у CSV/Parquet.

Конкретний приклад: порахувати середній рейтинг і кількість оцінок для кожного жанру в SQL дуже просто і часто швидше для великих batch-звітів:

```sql
SELECT
  g.name,
  COUNT(*) AS rating_count,
  AVG(r.rating) AS avg_rating
FROM ratings AS r
JOIN movie_genres AS mg ON mg.movie_id = r.movie_id
JOIN genres AS g ON g.genre_id = mg.genre_id
GROUP BY g.name
ORDER BY avg_rating DESC;
```

У Neo4j це теж можна зробити, але виконання йде через graph traversal `Genre <- HAS_GENRE - Movie <- RATED - User`. Для одноразового аналітичного звіту це нормально, але для регулярної звітності по всій таблиці ratings SQL-модель буде простішою, прозорішою і часто дешевшою в експлуатації.

Граф також програє там, де потрібна масова валідація, експорт або інтеграція з табличними інструментами. Якщо потрібно віддати всі рейтинги у вигляді плоскої таблиці для pandas, Spark, BI-системи або data warehouse, SQL-таблиця `ratings(user_id, movie_id, rating, timestamp)` зручніша за обхід мільйона ребер `RATED`. Реляційна модель також краще підходить для задач, де важлива сувора таблична нормалізація, транзакційні оновлення багатьох рядків за умовою, bulk load, auditing і прості foreign key constraints.

Ще одна слабка сторона графа в цьому датасеті - супервузли. Популярні фільми, жанри `Drama`/`Comedy` і дуже активні користувачі створюють вузли з великим degree. Індекс швидко знаходить стартовий вузол, але не скорочує кількість ребер, які треба обійти після цього. У SQL аналогічна проблема теж існує як skew у join-ах, але реляційні движки часто мають більш звичні інструменти для batch-агрегацій: partitioning, hash aggregation, parallel query, pre-aggregated tables. У графі такі вузли треба спеціально моделювати або обходити обережно.

## 3. Покращення схеми для запитів з частини 3

Для запиту 1 з частини 3, де шукаються `Thriller`-фільми із середнім рейтингом вище `4.0`, головна вартість - не знайти жанр, а пройти від усіх thriller-фільмів до всіх їхніх оцінок і порахувати `avg(r.rating)`. Це можна прискорити денормалізацією статистики на вузол `Movie`: додати властивості `ratingCount`, `avgRating`, `ratingSum` і оновлювати їх batch-скриптом після імпорту або інкрементно при додаванні рейтингу. Тоді запит стане значно дешевшим:

```cypher
MATCH (m:Movie)-[:HAS_GENRE]->(:Genre {name: "Thriller"})
WHERE m.avgRating > 4.0 AND m.ratingCount >= 20
RETURN m.movieId, m.title, m.year, m.avgRating, m.ratingCount
ORDER BY m.avgRating DESC, m.ratingCount DESC;
```

Це змінює trade-off. Запис і підтримка агрегатів стають складнішими, зате read-запит більше не обходить сотні тисяч `RATED` ребер. Для поточного графа краще рахувати агрегати напряму, бо це демонструє силу traversal. Для production-рекомендацій або dashboard-запитів попередньо обчислені агрегати були б практичнішими.

Для запиту 4 з частини 3, де рахуються жанри зі стабільно високими оцінками, проблема ще сильніша: `Genre -> Movie -> RATED` для `Drama` або `Comedy` розгортається у сотні тисяч оцінок. Тут краще застосувати дві зміни. Перша - зберігати агрегати на `Genre`, наприклад `ratingCount`, `avgRating`, `ratingStdDev`, `movieCount`. Друга - використати bucket-вузли для жанрів, як описано в частині 4: `(:Genre)-[:HAS_BUCKET]->(:GenreBucket {genre, decade})<-[:IN_GENRE_BUCKET]-(:Movie)`. Тоді запити можна робити не по всьому супержанру, а по менших сегментах, наприклад `Comedy` за 1990-ті або `Drama` за десятиліттями. Це не тільки прискорює обходи, а й робить аналітику змістовнішою.

Для запиту 5, рекомендації "користувачі зі схожими смаками також дивилися", найбільше прискорення дала б матеріалізація схожості користувачів. Зараз схожі користувачі обчислюються на льоту через шаблон `User -> liked Movie <- similar User`, що створює великі проміжні множини, особливо для популярних фільмів. Краща схема для частих рекомендацій:

```text
(:User)-[:SIMILAR {weight, updatedAt}]-(:User)
(:User)-[:LIKED {rating, timestamp}]->(:Movie)
```

`LIKED` можна створити для `rating >= 4` або `rating = 5`, щоб не фільтрувати кожне `RATED` ребро під час запиту. `SIMILAR` можна перераховувати batch-процесом, наприклад щодня або після імпорту. Тоді рекомендаційний запит починається не з мільйона `RATED`, а з обмеженої кількості найсхожіших користувачів:

```cypher
MATCH (:User {userId: 1})-[s:SIMILAR]-(similar:User)
WITH similar, s.weight AS similarity
ORDER BY similarity DESC
LIMIT 100
MATCH (similar)-[r:LIKED]->(candidate:Movie)
WHERE NOT EXISTS {
  MATCH (:User {userId: 1})-[:RATED]->(candidate)
}
RETURN candidate, count(*) AS recommendingUsers, sum(similarity) AS score
ORDER BY score DESC
LIMIT 20;
```

Це та сама ідея, яка буда застосована в GDS-частині для Louvain і Dijkstra. Спочатку матеріалізувати user-user similarity graph, а вже потім виконувати складніші алгоритми або рекомендації. Недолік - треба вирішити, як часто оновлювати `SIMILAR`, які пороги similarity використовувати і як не створити нові супервузли.

Для запиту 6, shortest path між користувачами через спільні фільми, схема `User-RATED-Movie` працює коректно, але шлях через популярні фільми може бути занадто "дешевим" і малоінформативним. Якщо два користувачі пов'язані через дуже популярний фільм, такий зв'язок слабший, ніж через рідкісний фільм зі специфічною аудиторією. Тому для якісніших shortest path запитів варто створити зважені user-user ребра `SIMILAR` і використовувати `distance = 1 / weight` або іншу формулу, яка штрафує надто популярні фільми. Тоді шлях інтерпретується не просто як "вони десь перетнулися через блокбастер", а як послідовність користувачів зі справді схожими смаками.

Загальний висновок: графова модель найсильніша там, де питання формулюється як traversal, similarity, recommendation, community або shortest path. Реляційна модель сильніша там, де питання формулюється як таблична агрегація, звіт, експорт або регулярна batch-аналітика по всіх рядках. Для MovieLens оптимальною була б гібридна архітектура: сирі рейтинги і звіти зберігати/рахувати у реляційній або аналітичній системі, а граф використовувати для рекомендацій, пояснюваних зв'язків, community detection і graph algorithms.
