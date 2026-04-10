from flask import Flask, jsonify, request
from flask_cors import CORS
from datasets import load_dataset
from gensim.models import Word2Vec as W2V
import numpy as np
import requests
import re
import threading

app = Flask(__name__)
CORS(app)

TMDB_API_KEY = 'a92262bee0938735682d46b631a3b5b6'
TMDB_BASE    = 'https://api.themoviedb.org/3'

filme_cache    = []
model_w2v      = None
vectori_filme  = {}
tmdb_cache     = {}

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


def construiesteCorpus(filme: list) -> list:
    corpus = []
    for film in filme:
        text = (
            f"{film.get('title', '')} "
            f"{film.get('plot_summary', '')} "
            f"{' '.join(film.get('genre_names', []))}"
        )
        corpus.append(tokenizeaza(text))
    return corpus


def antreneazaWord2Vec(corpus: list) -> W2V:
    model = W2V(
        corpus,
        vector_size=100,
        window=7,
        min_count=2,
        sg=1,
        workers=4,
        epochs=10
    )
    return model


def vectorFilm(tokeni: list, model: W2V) -> np.ndarray:
    vectori = [
        model.wv[t] for t in tokeni if t in model.wv
    ]
    if not vectori:
        return np.zeros(model.vector_size)
    return np.mean(vectori, axis=0)


def normalizeazaL2(vector: np.ndarray) -> np.ndarray:
    norma = np.linalg.norm(vector)
    if norma == 0:
        return vector
    return vector / norma


def construiesteVectoriFilme(filme: list, corpus: list, model: W2V) -> dict:
    vectori = {}
    for i, film in enumerate(filme):
        vec = vectorFilm(corpus[i], model)
        vectori[film['id']] = normalizeazaL2(vec)
    return vectori


def similaritateeCosinus(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    return float(np.dot(vec_a, vec_b))


def genereazaRecomandari(ids_lista: list, top_n: int = 20) -> list:
    if not ids_lista or not vectori_filme:
        return []

    vectori_valide = [
        vectori_filme[fid] for fid in ids_lista if fid in vectori_filme
    ]
    if not vectori_valide:
        return []

    profil    = normalizeazaL2(np.mean(vectori_valide, axis=0))
    set_lista = set(ids_lista)
    scoruri   = []

    for film in filme_cache:
        if film['id'] in set_lista:
            continue
        vec  = vectori_filme.get(film['id'])
        if vec is None:
            continue
        scor = similaritateeCosinus(profil, vec)
        scoruri.append((scor, film))

    scoruri.sort(key=lambda x: x[0], reverse=True)
    return [film for _, film in scoruri[:top_n]]


def parseazaCerere(text: str) -> dict:
    text_mic = text.lower()

    an = None
    match_an = re.search(r'\b(19[0-9]{2}|20[0-9]{2})\b', text)
    if match_an:
        an = int(match_an.group(1))

    deceniu = None
    match_dec = re.search(r'\b(19[0-9]0|20[0-9]0)s?\b', text_mic)
    if match_dec:
        deceniu = int(match_dec.group(1))

    dupa_an = None
    match_dupa = re.search(r'dup[aă]\s+(19[0-9]{2}|20[0-9]{2})', text_mic)
    if match_dupa:
        dupa_an = int(match_dupa.group(1))

    inainte_an = None
    match_inainte = re.search(r'[îi]nainte\s+de\s+(19[0-9]{2}|20[0-9]{2})', text_mic)
    if match_inainte:
        inainte_an = int(match_inainte.group(1))

    genuri_cautate = []
    harta_genuri_ro = {
        'actiune': 'Action', 'acțiune': 'Action',
        'comedie': 'Comedy', 'comic': 'Comedy',
        'horror': 'Horror', 'groaza': 'Horror', 'groază': 'Horror', 'teroare': 'Horror',
        'drama': 'Drama', 'dramă': 'Drama',
        'thriller': 'Thriller',
        'romantic': 'Romance', 'romantice': 'Romance', 'romance': 'Romance', 'dragoste': 'Romance',
        'animatie': 'Animation', 'animație': 'Animation', 'animat': 'Animation', 'desene': 'Animation',
        'documentar': 'Documentary', 'documentare': 'Documentary',
        'science fiction': 'Science Fiction', 'sf': 'Science Fiction', 'scifi': 'Science Fiction',
        'fantezie': 'Fantasy', 'fantasy': 'Fantasy', 'magie': 'Fantasy',
        'aventura': 'Adventure', 'aventură': 'Adventure', 'aventuri': 'Adventure',
        'mister': 'Mystery', 'mystery': 'Mystery',
        'muzical': 'Music', 'muzica': 'Music', 'muzică': 'Music',
        'razboi': 'War', 'război': 'War',
        'western': 'Western',
        'istoric': 'History', 'istorie': 'History',
        'biografic': 'Biography',
        'copii': 'Family', 'familie': 'Family', 'family': 'Family',
        'crime': 'Crime', 'crima': 'Crime', 'crimă': 'Crime', 'criminal': 'Crime',
    }
    for cuvant, gen_en in harta_genuri_ro.items():
        if cuvant in text_mic and gen_en not in genuri_cautate:
            genuri_cautate.append(gen_en)

    actori_cautati = []

    triggeruri_actor = [
        r'(?:with|starring|featuring|actor|actress|directed by|director)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})',
        r'(?:cu|regizat de|regizor|actor|actrita)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})',
    ]
    for pattern in triggeruri_actor:
        gasiti = re.findall(pattern, text)
        for a in gasiti:
            if a.strip() not in actori_cautati:
                actori_cautati.append(a.strip())

    toate_nume = re.findall(r'\b([A-Z][a-z]{1,}(?:\s+[A-Z][a-z]{1,}){1,2})\b', text)
    cuvinte_comune = {
        'Science Fiction', 'Action Movie', 'Horror Movie', 'Comedy Movie',
        'Tom Hanks', 'This Actor', 'Search Now', 'Natural Language',
    }
    for nume in toate_nume:
        if nume not in actori_cautati and nume not in cuvinte_comune:
            actori_cautati.append(nume)

    actori_cautati = [
        a for a in actori_cautati
        if not any(g.lower() in a.lower() for g in ['Fiction', 'Movie', 'Film', 'Actor', 'Language'])
    ]

    scor_min = None
    scor_max = None

    pattern_scor = [
        (r'(?:score|rating|rated|nota|notă|scor)\s*(?:above|over|bigger than|greater than|higher than|peste|mai mare|mai bun)\s*(\d+(?:\.\d+)?)', 'min'),
        (r'(?:above|over|bigger than|greater than|higher than|peste|mai mare|mai bun)\s*(?:a\s+)?(?:score|rating|nota|notă|scor)?\s*(?:of\s+)?(\d+(?:\.\d+)?)', 'min'),
        (r'(?:score|rating|rated|nota|notă|scor)\s*(?:below|under|less than|lower than|sub|mai mic|mai slab)\s*(\d+(?:\.\d+)?)', 'max'),
        (r'(?:at least|minimum|minim|cel puțin|cel putin)\s*(?:a\s+)?(?:score|rating|nota|notă|scor)?\s*(?:of\s+)?(\d+(?:\.\d+)?)', 'min'),
        (r'(?:score|rating|nota|notă|scor)\s*(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:or (?:above|more|higher)|sau mai (?:mare|bun|mult))', 'min'),
        (r'(?:score|rating|nota|notă|scor)\s*(?:between|intre|între)\s*(\d+(?:\.\d+)?)\s*(?:and|si|și)\s*(\d+(?:\.\d+)?)', 'range'),
    ]

    for pattern, tip in pattern_scor:
        match = re.search(pattern, text_mic)
        if match:
            if tip == 'min':
                val = float(match.group(1))
                scor_min = val if val <= 10 else val / 10
            elif tip == 'max':
                val = float(match.group(1))
                scor_max = val if val <= 10 else val / 10
            elif tip == 'range':
                v1 = float(match.group(1))
                v2 = float(match.group(2))
                scor_min = min(v1, v2) if min(v1, v2) <= 10 else min(v1, v2) / 10
                scor_max = max(v1, v2) if max(v1, v2) <= 10 else max(v1, v2) / 10
            break

    return {
        'an': an, 'deceniu': deceniu,
        'dupa_an': dupa_an, 'inainte_an': inainte_an,
        'genuri': genuri_cautate, 'actori': actori_cautati,
        'scor_min': scor_min, 'scor_max': scor_max,
    }


def filtreazaDupaMetadate(filme: list, cerere: dict) -> list:
    rezultat = []
    for film in filme:
        an_film = None
        if film.get('release_date'):
            try:
                an_film = int(film['release_date'][:4])
            except Exception:
                pass

        if cerere['an'] and an_film and an_film != cerere['an']:
            continue
        if cerere['deceniu'] and an_film:
            if not (cerere['deceniu'] <= an_film < cerere['deceniu'] + 10):
                continue
        if cerere['dupa_an'] and an_film and an_film <= cerere['dupa_an']:
            continue
        if cerere['inainte_an'] and an_film and an_film >= cerere['inainte_an']:
            continue
        if cerere['genuri']:
            genuri_film = [g.lower() for g in film.get('genre_names', [])]
            if not any(g.lower() in genuri_film for g in cerere['genuri']):
                continue
        if cerere['actori']:
            stars_film    = ' '.join(film.get('stars', [])).lower()
            director_film = (film.get('director') or '').lower()
            text_persoane = stars_film + ' ' + director_film
            potrivire = False
            for actor in cerere['actori']:
                parti = actor.lower().split()
                if any(p in text_persoane for p in parti if len(p) > 2):
                    potrivire = True
                    break
            if not potrivire:
                continue

        rating_film = float(film.get('vote_average') or 0)
        if cerere.get('scor_min') and rating_film < cerere['scor_min']:
            continue
        if cerere.get('scor_max') and rating_film > cerere['scor_max']:
            continue

        rezultat.append(film)
    return rezultat


def cautaDupaText(text: str, top_n: int = 20) -> list:
    if model_w2v is None or not vectori_filme:
        return []

    cerere    = parseazaCerere(text)
    candidati = filtreazaDupaMetadate(filme_cache, cerere)
    if not candidati:
        candidati = filme_cache

    tokeni = tokenizeaza(text)
    vec    = vectorFilm(tokeni, model_w2v)
    vec    = normalizeazaL2(vec)

    scoruri = []
    for film in candidati:
        vec_film = vectori_filme.get(film['id'])
        if vec_film is None:
            continue
        scor = similaritateeCosinus(vec, vec_film)

        bonus = 0.0
        if cerere['genuri']:
            genuri_film = [g.lower() for g in film.get('genre_names', [])]
            bonus += sum(1 for g in cerere['genuri'] if g.lower() in genuri_film) * 0.15
        if cerere['actori']:
            text_persoane = ' '.join(film.get('stars', [])).lower() + ' ' + (film.get('director') or '').lower()
            bonus += sum(1 for a in cerere['actori'] if a.lower() in text_persoane) * 0.2

        scoruri.append((scor + bonus, film))

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
            'id':            rand.get('movie_id', i),
            'title':         rand.get('title', ''),
            'plot_summary':  rand.get('plot_summary', ''),
            'genre_names':   genuri,
            'director':      rand.get('director', ''),
            'stars':         rand.get('stars') or [],
            'poster_path':   None,
            'backdrop_path': None,
            'vote_average':  0,
            'release_date':  '',
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
        res = requests.get(
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
    global filme_cache, model_w2v, vectori_filme

    if not filme_cache:
        filme_cache = incarcaFilmeHuggingFace(limita=500)

        print("Se construieste corpusul pentru Word2Vec...")
        corpus = construiesteCorpus(filme_cache)

        print(f"Se antreneaza Word2Vec pe {len(corpus)} filme (skip-gram, window=7)...")
        model_w2v = antreneazaWord2Vec(corpus)
        print(f"Vocabular Word2Vec: {len(model_w2v.wv)} cuvinte unice.")

        print("Se calculeaza vectorii pentru fiecare film...")
        vectori_filme = construiesteVectoriFilme(filme_cache, corpus, model_w2v)
        print("Word2Vec gata!")

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
    recomandari = genereazaRecomandari(date['lista'], top_n=20)
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


@app.route('/api/postere', methods=['GET'])
def getPostere():
    rezultat = {
        str(film['id']): film['poster_path']
        for film in filme_cache
        if film.get('poster_path')
    }
    return jsonify({'postere': rezultat, 'total': len(rezultat)})


if __name__ == '__main__':
    app.run(debug=True, port=5000)