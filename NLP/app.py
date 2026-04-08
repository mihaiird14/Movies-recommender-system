from flask import Flask, jsonify, request
from flask_cors import CORS
from datasets import load_dataset
import requests
import math
import re
import threading
from collections import defaultdict

app = Flask(__name__)
CORS(app)

TMDB_API_KEY = 'a92262bee0938735682d46b631a3b5b6'
TMDB_BASE    = 'https://api.themoviedb.org/3'

filme_cache   = []
matrice_tfidf = {}
idf_global    = {}
tmdb_cache    = {}

CUVINTE_STOP = {
    'the','a','an','and','or','but','in','on','at','to','for','of',
    'with','is','are','was','were','it','its','this','that','be','as',
    'by','from','has','have','had','he','she','they','we','you','i',
    'his','her','their','our','your','my','not','no','so','if','do',
    'does','did','can','could','will','would','may','might','must',
    'shall','should','about','into','through','during','before','after',
    'above','below','between','out','off','over','under','there','when',
    'where','who','which','what','how','him','them','its','been','being'
}


def tokenizeaza(text: str) -> list:
    text = text.lower()
    text = re.sub(r'[^a-z\s]', ' ', text)
    tokeni = text.split()
    return [t for t in tokeni if len(t) > 2 and t not in CUVINTE_STOP]


def calculeazaTF(tokeni: list) -> dict:
    if not tokeni:
        return {}
    tf = defaultdict(int)
    for t in tokeni:
        tf[t] += 1
    total = len(tokeni)
    return {t: count / total for t, count in tf.items()}


def calculeazaIDF(corpus: list) -> dict:
    N  = len(corpus)
    df = defaultdict(int)
    for tokeni in corpus:
        for t in set(tokeni):
            df[t] += 1
    return {t: math.log((N + 1) / (count + 1)) + 1 for t, count in df.items()}


def normalizeazaL2(vector: dict) -> dict:
    norma = math.sqrt(sum(v * v for v in vector.values()))
    if norma == 0:
        return vector
    return {t: v / norma for t, v in vector.items()}


def construiesteMatriceTFIDF(filme: list) -> dict:
    global idf_global
    corpus = []
    for film in filme:
        text = (
            f"{film.get('title', '')} "
            f"{film.get('plot_summary', '')} "
            f"{' '.join(film.get('genre_names', []))}"
        )
        corpus.append(tokenizeaza(text))

    idf_global = calculeazaIDF(corpus)

    matrice = {}
    for i, film in enumerate(filme):
        tf     = calculeazaTF(corpus[i])
        vector = {t: tf_val * idf_global.get(t, 1) for t, tf_val in tf.items()}
        matrice[film['id']] = normalizeazaL2(vector)

    return matrice


def similaritateeCosinus(vec_a: dict, vec_b: dict) -> float:
    dot = 0.0
    for termen, scor in vec_a.items():
        if termen in vec_b:
            dot += scor * vec_b[termen]
    return dot


def genereazaRecomandari(ids_lista: list, top_n: int = 20) -> list:
    if not ids_lista or not matrice_tfidf:
        return []

    profil = defaultdict(float)
    valide = 0
    for fid in ids_lista:
        vector = matrice_tfidf.get(fid)
        if vector:
            for termen, scor in vector.items():
                profil[termen] += scor
            valide += 1

    if valide == 0:
        return []

    profil    = {t: s / valide for t, s in profil.items()}
    set_lista = set(ids_lista)
    scoruri   = []

    for film in filme_cache:
        if film['id'] in set_lista:
            continue
        vector = matrice_tfidf.get(film['id'], {})
        scor   = similaritateeCosinus(profil, vector)
        scoruri.append((scor, film))

    scoruri.sort(key=lambda x: x[0], reverse=True)
    return [film for _, film in scoruri[:top_n]]


def cautaDupaText(text: str, top_n: int = 20) -> list:
    if not idf_global or not matrice_tfidf:
        return []

    tokeni = tokenizeaza(text)
    tf     = calculeazaTF(tokeni)
    vector = {t: tf_val * idf_global.get(t, 1) for t, tf_val in tf.items()}
    vector = normalizeazaL2(vector)

    scoruri = []
    for film in filme_cache:
        scor = similaritateeCosinus(vector, matrice_tfidf.get(film['id'], {}))
        scoruri.append((scor, film))

    scoruri.sort(key=lambda x: x[0], reverse=True)
    return [film for _, film in scoruri[:top_n]]


def incarcaFilmeHuggingFace(limita: int = 500) -> list:
    print("Se descarca dataset-ul de pe HuggingFace...")
    dataset = load_dataset(
        "krishnakamath/movielens-32m-movies-enriched-with-SIDs",
        split="train"
    )

    filme = []
    for i, rand in enumerate(dataset):
        if i >= limita:
            break

        genuri = rand.get('genres') or []
        if isinstance(genuri, str):
            genuri = [g.strip() for g in genuri.split('|') if g.strip()]

        film = {
            'id':             rand.get('movie_id', i),
            'title':          rand.get('title', ''),
            'plot_summary':   rand.get('plot_summary', ''),
            'genre_names':    genuri,
            'director':       rand.get('director', ''),
            'stars':          rand.get('stars') or [],
            'poster_path':    None,
            'backdrop_path':  None,
            'vote_average':   0,
            'release_date':   '',
        }
        filme.append(film)

    print(f"Incarcate {len(filme)} filme din HuggingFace.")
    return filme


def curataTitlu(titlu: str) -> tuple:
    match = re.match(r'^(.*?)\s*\((\d{4})\)\s*$', titlu.strip())
    if match:
        return match.group(1).strip(), match.group(2)
    return titlu.strip(), None


def cautaTMDB(titlu: str) -> dict:
    titlu_curat, an = curataTitlu(titlu)
    try:
        params = {'api_key': TMDB_API_KEY, 'query': titlu_curat, 'language': 'ro-RO'}
        if an:
            params['year'] = an

        res       = requests.get(f"{TMDB_BASE}/search/movie", params=params, timeout=5)
        rezultate = res.json().get('results', [])

        if not rezultate and an:
            params.pop('year')
            res       = requests.get(f"{TMDB_BASE}/search/movie", params=params, timeout=5)
            rezultate = res.json().get('results', [])

        if not rezultate:
            return {}

        primul = rezultate[0]
        return {
            'tmdb_id':       primul.get('id'),
            'poster_path':   primul.get('poster_path'),
            'backdrop_path': primul.get('backdrop_path'),
            'vote_average':  primul.get('vote_average', 0),
            'release_date':  primul.get('release_date', ''),
        }
    except Exception:
        return {}


def luaDistributie(tmdb_id: int) -> list:
    try:
        res  = requests.get(
            f"{TMDB_BASE}/movie/{tmdb_id}/credits",
            params={'api_key': TMDB_API_KEY, 'language': 'ro-RO'},
            timeout=5
        )
        return (res.json().get('cast') or [])[:6]
    except Exception:
        return []


def imbogatesteUnFilm(film: dict):
    fid  = film['id']
    tmdb = cautaTMDB(film['title'])
    tmdb_cache[fid]       = tmdb
    film['poster_path']   = tmdb.get('poster_path')
    film['backdrop_path'] = tmdb.get('backdrop_path')
    film['vote_average']  = tmdb.get('vote_average', 0)
    film['release_date']  = tmdb.get('release_date', '')
    film['tmdb_id']       = tmdb.get('tmdb_id')


def imbogatesteRestulInFundal(filme: list, start: int):
    print(f"Thread fundal: imbogatesc filmele {start}-{len(filme)}...")
    for film in filme[start:]:
        try:
            imbogatesteUnFilm(film)
        except Exception:
            pass
    print("Thread fundal: gata cu toate posterele!")


@app.route('/api/filme', methods=['GET'])
def getFilme():
    global filme_cache, matrice_tfidf

    if not filme_cache:
        filme_cache   = incarcaFilmeHuggingFace(limita=500)
        print(f"Se construieste TF-IDF pentru {len(filme_cache)} filme...")
        matrice_tfidf = construiesteMatriceTFIDF(filme_cache)

        print("Se imbogatesc primele 50 filme cu postere TMDB...")
        for film in filme_cache[:50]:
            try:
                imbogatesteUnFilm(film)
            except Exception:
                pass

        thread = threading.Thread(
            target=imbogatesteRestulInFundal,
            args=(filme_cache, 50),
            daemon=True
        )
        thread.start()
        print("Gata! Restul posterelor se incarca in fundal.")

    return jsonify({'filme': filme_cache, 'total': len(filme_cache)})


@app.route('/api/recomandari', methods=['POST'])
def getRecomandari():
    date = request.get_json()
    if not date or 'lista' not in date:
        return jsonify({'eroare': 'Lipseste campul lista'}), 400

    ids_lista   = date['lista']
    recomandari = genereazaRecomandari(ids_lista, top_n=20)
    return jsonify({'recomandari': recomandari, 'total': len(recomandari)})


@app.route('/api/cauta', methods=['POST'])
def getCautareNaturala():
    date = request.get_json()
    if not date or 'text' not in date:
        return jsonify({'eroare': 'Lipseste campul text'}), 400

    rezultate = cautaDupaText(date['text'], top_n=20)
    return jsonify({'rezultate': rezultate, 'total': len(rezultate)})


@app.route('/api/film/<int:film_id>', methods=['GET'])
def getDetaliiFilm(film_id):
    film = next((f for f in filme_cache if f['id'] == film_id), None)
    if not film:
        return jsonify({'eroare': 'Film negasit'}), 404

    if film_id not in tmdb_cache:
        tmdb_cache[film_id] = cautaTMDB(film['title'])

    tmdb        = tmdb_cache[film_id]
    distributie = []
    if tmdb.get('tmdb_id'):
        distributie = luaDistributie(tmdb['tmdb_id'])

    detalii = {
        'id':            film['id'],
        'title':         film['title'],
        'overview':      film['plot_summary'],
        'genres':        [{'name': g} for g in film['genre_names']],
        'director':      film['director'],
        'stars':         film['stars'],
        'poster_path':   tmdb.get('poster_path'),
        'backdrop_path': tmdb.get('backdrop_path'),
        'vote_average':  tmdb.get('vote_average', 0),
        'release_date':  tmdb.get('release_date', ''),
    }

    return jsonify({'detalii': detalii, 'distributie': {'cast': distributie}})


@app.route('/api/genuri', methods=['GET'])
def getGenuri():
    genuri = sorted(set(
        g for film in filme_cache for g in film.get('genre_names', [])
    ))
    return jsonify({'genuri': genuri})


if __name__ == '__main__':
    app.run(debug=True, port=5000)