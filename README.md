# ◈ CineMatch

**A Word2Vec-Based Movie Recommendation and Natural Language Search System**

CineMatch is a full-stack web application built as an NLP university project. It combines a Word2Vec semantic embedding model trained on film metadata with a Flask REST backend and a responsive dark-theme frontend. Users can browse films, maintain a personal watchlist, receive personalised recommendations, and search for films using free-form natural language descriptions in English or Romanian.

---

## Features

- **Discover** — browse a catalogue of 500 films loaded from the MovieLens 32M dataset
- **My List** — save films to a personal watchlist (persisted in browser localStorage)
- **Recommendations** — receive top-20 film recommendations based on your watchlist, computed via cosine similarity on Word2Vec vectors
- **NLP Search** — describe what you want in natural language; the system parses genre, year, decade, actor, director, and rating constraints, then ranks results semantically
- **Word2Vec vs SBERT** — switch between two NLP algorithms in the search interface and compare results
- **Progressive poster loading** — posters are fetched from TMDB in the background and updated automatically without reloading the page

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| NLP engine | Python, Gensim Word2Vec, Sentence-Transformers (SBERT) |
| Backend | Flask, Flask-CORS |
| Data | HuggingFace Datasets (MovieLens 32M enriched) |
| Visual metadata | TMDB API |
| Frontend | HTML5, CSS3, Vanilla JavaScript (ES6+) |
| Vectors | NumPy |

---

## Project Structure

```
cinematch/
├── app.py          # Flask server — NLP logic, REST API endpoints
├── index.html      # Single-page application shell
├── script.js       # Frontend logic (fetch, DOM, localStorage, polling)
├── stil.css        # Dark cinema UI styles
└── requirements.txt
```

---

## Installation

### Prerequisites

- Python 3.9+
- A TMDB API key (free at [themoviedb.org](https://www.themoviedb.org/documentation/api))

### Steps

**1. Clone the repository**
```bash
git clone https://github.com/your-username/cinematch.git
cd cinematch
```

**2. Install Python dependencies**
```bash
pip install -r requirements.txt
```

**3. Add your TMDB API key**

Open `app.py` and replace the value of `TMDB_API_KEY`:
```python
TMDB_API_KEY = 'your_api_key_here'
```

**4. Start the Flask server**
```bash
python app.py
```

The first startup takes **1–3 minutes** — the server downloads the HuggingFace dataset, trains Word2Vec, and computes film vectors. Subsequent startups reuse HuggingFace's local cache and are faster.

**5. Serve the frontend**

Open a second terminal in the same folder:
```bash
python -m http.server 8080
```

**6. Open in browser**
```
http://localhost:8080
```

---

## How It Works

### NLP Pipeline

```
Film text (title + plot + genres)
        ↓
   tokenizeaza()        lowercase, remove punctuation, filter stopwords
        ↓
 antreneazaWord2Vec()   skip-gram, vector_size=100, window=7, epochs=10
        ↓
    vectorFilm()        mean of token vectors → 100-dim numpy array
        ↓
  normalizeazaL2()      divide by L2 norm → unit vector
        ↓
similaritateeCosinus()  dot product (= cosine similarity for unit vectors)
```

### Recommendations

1. JS reads the user's watchlist IDs from `localStorage`
2. POST to `/api/recomandari` with the ID list
3. Flask computes the **user profile** = L2-normalised mean of watchlist vectors
4. Cosine similarity is computed between the profile and every other film
5. Top 20 films are returned and rendered as cards

### NLP Search

1. User types a free-text query (e.g. `"horror movies with a serial killer after 2000"`)
2. `parseazaCerere()` extracts structured constraints via regex (year, decade, genre, actor, rating)
3. `filtreazaDupaMetadate()` removes films that fail hard constraints
4. The query is tokenised and projected into the Word2Vec space
5. Cosine similarity is computed against remaining candidates
6. Genre matches add **+0.15** bonus per genre; actor/director matches add **+0.20** bonus per person
7. Results are sorted by total score and top 20 are returned

### Word2Vec vs SBERT

| | Word2Vec | SBERT |
|--|----------|-------|
| Unit | individual words | entire sentence |
| Vector | mean of word vectors | single sentence embedding |
| Multilingual | ❌ (English only) | ✅ (Romanian supported) |
| Load time | fast (trained at startup) | slower (~120 MB model download) |
| Accuracy on complex queries | moderate | higher |

SBERT loads in the background after Word2Vec is ready. The frontend shows a `loading...` badge that turns `ready` when SBERT becomes available.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/filme` | Load all films, train Word2Vec, return catalogue |
| POST | `/api/recomandari` | Top-20 recommendations for a watchlist |
| POST | `/api/cauta` | NLP search (`{ "text": "...", "algoritm": "word2vec" or "sbert" }`) |
| GET | `/api/film/<id>` | Full film details + cast from TMDB |
| GET | `/api/genuri` | Sorted list of unique genres |
| GET | `/api/postere` | Map of film_id to poster_path for background polling |
| GET | `/api/status` | `{ "word2vec": true, "sbert": true/false }` |

---

## Known Limitations

- **Small corpus** — only 500 of 87,000 available films are loaded. Increase the `limita` parameter in `incarcaFilmeHuggingFace()` to load more (slower startup).
- **English descriptions** — Word2Vec is trained on English text. Romanian queries work for genre/metadata filtering but semantic matching is limited. SBERT handles Romanian natively.
- **localStorage** — watchlists are stored in the browser and are lost if the cache is cleared. No cross-device sync.
- **TMDB dependency** — posters and ratings require an active internet connection and a valid API key.
- **No GPU** — training is CPU-only; acceptable at 500 films but slow at full scale.

---

## Dataset

**MovieLens 32M Movies Enriched** by krishnakamath, available on HuggingFace:
```
krishnakamath/movielens-32m-movies-enriched-with-SIDs
```
Contains ~87,000 films with title, plot summary, genres, director, and cast.

Visual metadata (posters, ratings, backdrops) is sourced from **The Movie Database (TMDB)** via their free public API.

---

## Requirements

```
flask
flask-cors
requests
datasets
gensim
numpy
sentence-transformers
```

Install with:
```bash
pip install -r requirements.txt
```
