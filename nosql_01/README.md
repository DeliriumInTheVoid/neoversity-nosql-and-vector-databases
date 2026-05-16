# Spotify Tracks MongoDB Project

Проєкт завантажує Spotify Tracks Dataset у MongoDB Atlas або локальний MongoDB у Docker, перетворює сирий CSV у документоорієнтовану колекцію `tracks`, виконує запити та аналізує індекси через `explain()`.

## Структура

```text
nosql_01/
├── .env
├── .env.example
├── .gitignore
├── docker-compose.yml
├── dataset/
│   └── dataset.csv
├── requirements.txt
├── scripts/
│   ├── 01_load_data.py
│   └── 02_transform.js
├── queries/
│   ├── part2_queries.js
│   ├── part3_aggregations.js
│   └── part4_indexes.js
├── queries_result/
│   ├── part2_queries.txt
│   ├── part3_aggregations.txt
│   └── part4_indexes.txt
├── images/
│   ├── 00_atlas_initial.png
│   ├── 01_atlas_load_cloud.png
│   ├── 01_atlas_load_script.png
│   ├── 02_atlas_transform_cloud.png
│   ├── 02_atlas_transform_script.png
│   └── 04_atlas_indexes_cloud.png
└── README.md
```

## Запуск з нуля

Усі команди нижче виконуються з кореня `nosql_01`. Сценарій можна виконати як локальний MongoDB у Docker, це дає відтворюваний інстанс бази без залежності від Atlas або встановленого `mongosh` на хості, або локально із встановленим `mongosh`.

### MongoDB Docker

1. Запустити MongoDB контейнер:

```powershell
docker compose up -d
docker compose ps
```

Очікуваний стан контейнера: `nosql_01_mongo` має бути `healthy`.

2. Створити `.env` для підключення до локального Docker MongoDB:

```env
MONGO_URI=mongodb://root:example@localhost:27017/spotify?authSource=admin
```

3. Створити та активувати Python env для завантаження CSV:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

4. Встановити Python залежності:

```powershell
pip install -r requirements.txt
```

5. Завантажити CSV у `spotify.tracks_raw` локального MongoDB інстансу:

```powershell
python scripts/01_load_data.py
```

6. Побудувати фінальну колекцію `spotify.tracks` через `mongosh` всередині Docker-контейнера:

```powershell
docker compose exec -T mongo mongosh "mongodb://root:example@localhost:27017/spotify?authSource=admin" --file /workspace/scripts/02_transform.js
```

Очікуваний результат: `Transformed documents in tracks: 113999`.

7. Запустити запити частини 2:

```powershell
docker compose exec -T mongo mongosh "mongodb://root:example@localhost:27017/spotify?authSource=admin" --file /workspace/queries/part2_queries.js
```

8. Запустити аналітичні pipeline частини 3:

```powershell
docker compose exec -T mongo mongosh "mongodb://root:example@localhost:27017/spotify?authSource=admin" --file /workspace/queries/part3_aggregations.js
```

9. Запустити аналіз індексів та `explain()` частини 4:

```powershell
docker compose exec -T mongo mongosh "mongodb://root:example@localhost:27017/spotify?authSource=admin" --file /workspace/queries/part4_indexes.js
```

10. За потреби перевірити кількість документів у контейнері:

```powershell
docker compose exec -T mongo mongosh "mongodb://root:example@localhost:27017/spotify?authSource=admin" --quiet --eval "db.getSiblingDB('spotify').tracks.countDocuments()"
```

Щоб повністю очистити локальну MongoDB разом із Docker volume:

```powershell
docker compose down -v
```

### MongoDB Atlas

Скрипти також працюють з Atlas. Для цього в `.env` потрібно замінити локальний URI на Atlas connection string:

```env
MONGO_URI=mongodb+srv://<user>:<password>@<cluster>/<database>?retryWrites=true&w=majority
```

Після цього `python scripts/01_load_data.py` завантажить CSV в Atlas. Для js скриптів потрібен локально встановлений `mongosh` або запуск із середовища, де він доступний:

```powershell
$env:MONGO_URI = ((Get-Content .env | Where-Object { $_ -match '^MONGO_URI=' }) -replace '^MONGO_URI=', '').Trim('"')
mongosh "$env:MONGO_URI" --file scripts/02_transform.js
mongosh "$env:MONGO_URI" --file queries/part2_queries.js
mongosh "$env:MONGO_URI" --file queries/part3_aggregations.js
mongosh "$env:MONGO_URI" --file queries/part4_indexes.js
```

## Схема колекції `tracks`

Після трансформації кожен документ має таку логіку:

```json
{
  "_id": "ObjectId",
  "track_id": "5SuOikwiRyPMVoIQDJUgSV",
  "track_name": "Comedy",
  "album_name": "Comedy",
  "explicit": false,
  "popularity": 73,
  "duration_ms": 230666,
  "track_genre": "acoustic",
  "artists": ["Gen Hoshino"],
  "audio_features": {
    "danceability": 0.676,
    "energy": 0.461,
    "loudness": -6.746,
    "speechiness": 0.143,
    "acousticness": 0.0322,
    "instrumentalness": 0.00000101,
    "liveness": 0.358,
    "valence": 0.715,
    "tempo": 87.917,
    "key": 1,
    "mode": 0,
    "time_signature": 4
  },
  "duration_sec": 230.7,
  "popularity_tier": "high"
}
```

`audio_features` містить усі аудіо-характеристики, `artists` є масивом виконавців, `duration_sec` є обчисленим полем, а `popularity_tier` ділить треки на `high`, `medium`, `low`.

## Частина 1. Питання

### 1. Чому `audio_features` вкладені в окремий об'єкт?

Характеристики аудіо описують таку підсутність треку як "звучання". Тому поля `danceability`, `energy`, `tempo`, `valence`, `loudness` та інші логічно зберігати разом у `audio_features`. Це робить документ читабельнішим і дає зрозумілі шляхи для запитів, наприклад `"audio_features.danceability": { $gt: 0.7 }`.

Таке вкладення вигідне, коли група полів часто читається разом і належить до одного об'єкта. Проблеми можуть з'явитися, якщо вкладених полів дуже багато, вони мають різні життєві цикли або потребують окремих прав доступу та оновлень. У нашому випадку властивості аудіо стабільні й належать самому треку, тому вкладення доречне.

### 2. Чому `artists` зберігаються як масив?

Один трек може мати кількох виконавців, а масив дає змогу працювати з ними як з окремими значеннями. Запити на кшталт `find({ artists: "Gen Hoshino" })` стають простими, без ручного парсингу рядка. Також можна використовувати `$unwind`, щоб порахувати статистику для кожного артиста окремо. Наприклад кількість треків, середню популярність, мінімальну популярність.

Якби артисти лишилися рядком з `;`, то довелося б використовувати regex або розбивати рядки в кожному запиті.

### 3. Що таке `$out` і чим він відрізняється від `$merge`?

`$out` записує результат aggregation pipeline у колекцію. Якщо колекція вже існує, вона замінюється результатом пайплайна. У цьому проєкті `$out: "tracks"` підходить, бо ми хочемо повністю перебудувати `tracks` із `tracks_raw` і отримати чисту повторювану трансформацію.

`$merge` не обов'язково замінює всю колекцію. Він може вставляти нові документи, оновлювати наявні або комбінувати поведінку залежно від `on`, `whenMatched`, `whenNotMatched`. `$merge` варто використовувати для інкрементальних оновлень, коли не потрібно перезаписувати всю колекцію.

## Частина 2. Запити

Скрипт: `queries/part2_queries.js`.

1. Треки для вечірки: фільтр за `"audio_features.danceability" > 0.7`, `"audio_features.energy" > 0.7`, `duration_ms` у межах 180000-300000.
2. Виконавці, у яких усі треки популярні: `$unwind` масиву `artists`, групування за артистом, `track_count >= 3`, `min_popularity >= 60`.
3. Нетипові треки: групування за жанром, розрахунок `$avg` і `$stdDevPop` для `tempo`, поріг `avg + 2 * stdDev`.
4. Треки для фонової роботи: `loudness < -10`, `speechiness < 0.1`, `instrumentalness > 0.5`, `explicit: false`.

### 1. Для чого використовується `$unwind`?

`$unwind` розгортає масив у кілька документів. Якщо трек має `artists: ["A", "B"]`, після `$unwind: "$artists"` він тимчасово стає двома документами. Один для артиста `A`, другий для артиста `B`. Це потрібно, коли статистику треба рахувати не по треку, а по кожному елементу масиву окремо. У запитах для артистів без `$unwind` було б складно коректно порахувати кількість треків і середню популярність для кожного виконавця.

### 2. Чим `$stdDevPop` відрізняється від `$stdDevSamp`?

`$stdDevPop` рахує стандартне відхилення для всієї генеральної сукупності. У нашому завданні для кожного жанру ми беремо всі треки цього жанру з датасету, тому `$stdDevPop` логічний.

`$stdDevSamp` рахує вибіркове стандартне відхилення і використовує поправку Бесселя. Його краще брати, коли дані є лише вибіркою з більшої невідомої сукупності, і треба оцінити розкид у всій популяції.

## Частина 3. Аналітика

Скрипт: `queries/part3_aggregations.js`.

1. Топ-10 виконавців за середньою популярністю: `$unwind`, `$group`, фільтр `track_count >= 5`, сортування за `avg_popularity`.
2. Розподіл за настроєм: `valence` і `energy` порівнюються з порогом `0.5`; категорії `happy`, `angry`, `calm`, `sad`.
3. Найбільш танцювальний жанр: групування за `track_genre`, `track_count >= 100`, середні `danceability`, `energy`, `valence`. У фінальному кроці додано `$lookup`, щоб показати кілька прикладів найтанцювальніших треків цього жанру.

### 1. Що буде, якщо змінити поріг кількості треків для артистів?

Якщо знизити поріг із 5 до 1, у результат потрапить багато виконавців з одним треком. Їхня середня популярність дорівнюватиме популярності одного треку, тому топ може стати випадковішим, тобто артист із одним дуже популярним треком обжене стабільного артиста з великим каталогом.

Якщо підняти поріг до більш ніж 50 треків, залишаться лише артисти з великою кількістю записів у датасеті. Результат стане стабільнішим статистично, але може втратити нішевих або нових артистів. Середня популярність також може знизитися, бо у великих каталогах часто є як хіти, так і менш популярні треки.

### 2. Чи зміниться результат для жанрів, якщо поріг знизити зі 100 до 50?

Може змінитися, якщо в датасеті є жанри з 50-99 треками та високою середньою `danceability`. З нижчим порогом у конкуренцію потрапляє більше жанрів, але оцінка стає менш надійною, бо менша кількість треків сильніше реагує на викиди. Поріг 100 балансує повноту й статистичну стабільність.

## Частина 4. Індекси та `explain()`

Скрипт: `queries/part4_indexes.js`.

### Завдання 1. Індекс для pop + danceability + sort popularity

Запит:

```javascript
db.tracks.find({
  track_genre: "pop",
  "audio_features.danceability": { $gte: 0.7 }
}).sort({ popularity: -1 }).toArray();
```

Створений індекс:

```javascript
db.tracks.createIndex(
  {
    track_genre: 1,
    popularity: -1,
    "audio_features.danceability": 1
  },
  { name: "idx_tracks_genre_popularity_danceability" }
);
```

Порядок полів обраний за правилом ESR: equality `track_genre`, sort `popularity`, range `"audio_features.danceability"`. До індексу типовий план має `COLLSCAN` і великий `totalDocsExamined`. Після створення індексу план має містити `IXSCAN`, `indexesUsed: ["idx_tracks_genre_popularity_danceability"]`, а `totalKeysExamined` та `totalDocsExamined` мають бути значно меншими.

Зафіксований результат:

```json
{
  "before": {
    "nReturned": 354,
    "winningStages": ["SORT", "COLLSCAN"],
    "indexesUsed": [],
    "totalKeysExamined": 0,
    "totalDocsExamined": 113999,
    "executionTimeMillis": 75
  },
  "after": {
    "nReturned": 354,
    "winningStages": ["FETCH", "IXSCAN"],
    "indexesUsed": ["idx_tracks_genre_popularity_danceability"],
    "totalKeysExamined": 412,
    "totalDocsExamined": 354,
    "executionTimeMillis": 2
  }
}
```

Зміна в плані: замість повного сканування `COLLSCAN` і сортування в пам'яті MongoDB використовує `IXSCAN` по `idx_tracks_genre_popularity_danceability`, а потім `FETCH` для читання повних документів. Індекс використовується, бо у `winningStages` є `IXSCAN`, а `indexesUsed` містить назву створеного індексу.

### Завдання 2. Індекс для музики для роботи

Запит:

```javascript
db.tracks.find({
  explicit: false,
  "audio_features.instrumentalness": { $gt: 0.5 },
  "audio_features.speechiness": { $lt: 0.1 }
});
```

Створений індекс:

```javascript
db.tracks.createIndex(
  {
    explicit: 1,
    "audio_features.instrumentalness": -1,
    "audio_features.speechiness": 1
  },
  { name: "idx_tracks_work_music" }
);
```

`explicit` стоїть першим, бо це точна умова. Далі йдуть числові поля з діапазонами. Після створення індексу `explain()` має показати `IXSCAN` та `indexesUsed: ["idx_tracks_work_music"]`.

Зафіксований результат:

```json
{
  "before": {
    "nReturned": 16141,
    "winningStages": ["COLLSCAN"],
    "indexesUsed": [],
    "totalKeysExamined": 0,
    "totalDocsExamined": 113999,
    "executionTimeMillis": 143
  },
  "after": {
    "nReturned": 16141,
    "winningStages": ["FETCH", "IXSCAN"],
    "indexesUsed": ["idx_tracks_work_music"],
    "totalKeysExamined": 16602,
    "totalDocsExamined": 16141,
    "executionTimeMillis": 35
  }
}
```

Після індексації MongoDB не читає всі 113999 документів. План використовує `IXSCAN` по `idx_tracks_work_music`, а `indexBounds` обмежують `explicit`, `"audio_features.instrumentalness"` і `"audio_features.speechiness"`.

### Завдання 3. Чи є запит покривним?

Запит:

```javascript
db.tracks.find({
  track_genre: "pop",
  popularity: { $gte: 70 }
});
```

У такому вигляді запит не є покривним. Хоча індекс із завдання 1 містить `track_genre`, `popularity` і `"audio_features.danceability"`, сам `find()` без проєкції повертає повний документ. Повний документ містить `track_name`, `album_name`, `artists`, `audio_features` та інші поля, яких немає в індексі. Через це MongoDB має виконати `FETCH`, тобто прочитати документи з колекції після проходу по індексу.

Запит міг би стати покривним, якби проєкція обмежувалася лише полями індексу й виключала `_id`, наприклад:

```javascript
db.tracks.find(
  {
    track_genre: "pop",
    popularity: { $gte: 70 }
  },
  {
    _id: 0,
    track_genre: 1,
    popularity: 1,
    "audio_features.danceability": 1
  }
);
```

У перевірці покривний варіант показав:

```json
{
  "original_without_projection": {
    "nReturned": 317,
    "winningStages": ["FETCH", "IXSCAN"],
    "indexesUsed": ["idx_tracks_genre_popularity_danceability"],
    "totalKeysExamined": 317,
    "totalDocsExamined": 317
  },
  "covered_variant_with_projection": {
    "nReturned": 317,
    "winningStages": ["PROJECTION_DEFAULT", "IXSCAN"],
    "indexesUsed": ["idx_tracks_genre_popularity_danceability"],
    "totalKeysExamined": 317,
    "totalDocsExamined": 0
  }
}
```

`totalDocsExamined: 0` у другому варіанті підтверджує, що MongoDB змогла відповісти тільки з індексу. Оригінальний запит без проєкції не покривний, бо має `FETCH` і `totalDocsExamined: 317`.
