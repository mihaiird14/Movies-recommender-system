const API = 'http://localhost:5000/api';
const TMDB_IMG = 'https://image.tmdb.org/t/p/';
let utilizatorCurent = null;
let toateFilmele     = [];
let filmeFiltrate    = [];
let numarAfisat      = 0;
let genActiv         = null;
let filmModalCurent  = null;
const MARIME_PAGINA  = 24;
const ecranAuth      = document.getElementById('autentificare');
const ecranApp       = document.getElementById('aplicatie');
const campUtilizator = document.getElementById('utilizator');
const butonIntra     = document.getElementById('butonIntra');
const mesaj          = document.getElementById('mesaj');
const numeAfisat     = document.getElementById('nume');
const avatarEl       = document.getElementById('avatar');
const contorEl       = document.getElementById('contor');
const butonIesire    = document.getElementById('butonIesire');
const butonNavs      = document.querySelectorAll('.buton-nav');
const grilaFilme     = document.getElementById('grila-filme');
const grilaLista     = document.getElementById('grila-lista');
const grilaRec       = document.getElementById('grila-recomandari');
const golRec         = document.getElementById('gol-recomandari');
const butonMaiMulte  = document.getElementById('butonMaiMulte');
const campCautare    = document.getElementById('camp-cautare');
const containerGenuri= document.getElementById('genuri');
const modal          = document.getElementById('modal');
const butonInchide   = document.getElementById('butonInchide');
const butonLista     = document.getElementById('butonLista');


function luaUtilizatori() {
  return JSON.parse(localStorage.getItem('cm_utilizatori') || '{}');
}

function salveazaUtilizatori(u) {
  localStorage.setItem('cm_utilizatori', JSON.stringify(u));
}

function luaDateUtilizator(username) {
  const utilizatori = luaUtilizatori();
  if (!utilizatori[username]) {
    utilizatori[username] = { lista: [] };
    salveazaUtilizatori(utilizatori);
  }
  return utilizatori[username];
}

function salveazaDateUtilizator(date) {
  const utilizatori = luaUtilizatori();
  utilizatori[utilizatorCurent] = date;
  salveazaUtilizatori(utilizatori);
}

function luaLista() {
  return luaDateUtilizator(utilizatorCurent).lista || [];
}

function toggleLista(filmId) {
  const date = luaDateUtilizator(utilizatorCurent);
  const idx  = date.lista.indexOf(filmId);
  if (idx === -1) date.lista.push(filmId);
  else date.lista.splice(idx, 1);
  salveazaDateUtilizator(date);
  actualizeazaContor();
  return idx === -1;
}

function esteInLista(filmId) {
  return luaLista().includes(filmId);
}

function actualizeazaContor() {
  const n = luaLista().length;
  contorEl.textContent = `${n} film${n !== 1 ? 'e' : ''} salvat${n !== 1 ? 'e' : ''}`;
}

butonIntra.addEventListener('click', faceLogin);
campUtilizator.addEventListener('keydown', e => { if (e.key === 'Enter') faceLogin(); });

function faceLogin() {
  const val = campUtilizator.value.trim().toLowerCase();
  if (!val)        { mesaj.textContent = 'Introdu un username!'; return; }
  if (val.length < 3) { mesaj.textContent = 'Minimum 3 caractere.'; return; }
  utilizatorCurent = val;
  luaDateUtilizator(val);
  intraInApp();
}

function intraInApp() {
  ecranAuth.classList.remove('activ');
  ecranApp.classList.add('activ');
  numeAfisat.textContent  = utilizatorCurent;
  avatarEl.textContent    = utilizatorCurent[0].toUpperCase();
  actualizeazaContor();
  incarcaFilme();
}

butonIesire.addEventListener('click', faceLogout);

function faceLogout() {
  utilizatorCurent = null;
  ecranApp.classList.remove('activ');
  ecranAuth.classList.add('activ');
  campUtilizator.value = '';
  mesaj.textContent    = '';
  toateFilmele  = [];
  filmeFiltrate = [];
  numarAfisat   = 0;
  genActiv      = null;
  seteazaSectiune('descoperire');
}


butonNavs.forEach(btn => {
  btn.addEventListener('click', () => seteazaSectiune(btn.dataset.sectiune));
});

function seteazaSectiune(sectiune) {
  butonNavs.forEach(b => b.classList.toggle('activ', b.dataset.sectiune === sectiune));
  document.querySelectorAll('.sectiune').forEach(s => s.classList.remove('activa'));
  document.getElementById(sectiune).classList.add('activa');
  if (sectiune === 'lista')       afiseazaLista();
  if (sectiune === 'recomandari') incarcaRecomandari();
}

async function incarcaFilme() {
  grilaFilme.innerHTML = `
    <div class="incarcare">
      <div id="roata"></div>
      <p>Se încarcă filmele...</p>
    </div>`;

  try {
    const raspuns = await fetch(`${API}/filme`);
    const date    = await raspuns.json();
    toateFilmele  = date.filme || [];
    filmeFiltrate = [...toateFilmele];
    numarAfisat   = 0;

    construiesteGenuri();
    afiseazaGrilaFilme();
  } catch(e) {
    grilaFilme.innerHTML = `
      <div class="gol">
        <div class="icon-gol">⚠</div>
        <p>Nu pot conecta la server.<br/>Rulează <strong>python app.py</strong> și reîncarcă pagina.</p>
      </div>`;
    butonMaiMulte.style.display = 'none';
  }
}


async function construiesteGenuri() {
  try {
    const raspuns = await fetch(`${API}/genuri`);
    const date    = await raspuns.json();
    const eticheta = containerGenuri.querySelector('#eticheta-genuri');
    containerGenuri.innerHTML = '';
    containerGenuri.appendChild(eticheta);

    (date.genuri || []).forEach(gen => {
      const btn = document.createElement('button');
      btn.className   = 'chip-gen';
      btn.textContent = gen;
      btn.addEventListener('click', () => {
        if (genActiv === gen) {
          genActiv = null;
          btn.classList.remove('activ');
        } else {
          genActiv = gen;
          document.querySelectorAll('.chip-gen').forEach(c => c.classList.remove('activ'));
          btn.classList.add('activ');
        }
        aplicaFiltre();
      });
      containerGenuri.appendChild(btn);
    });
  } catch(e) {}
}


campCautare.addEventListener('input', aplicaFiltre);

function aplicaFiltre() {
  const query = campCautare.value.toLowerCase().trim();
  filmeFiltrate = toateFilmele.filter(film => {
    const potriviteCautare = !query ||
      film.title.toLowerCase().includes(query) ||
      (film.overview || '').toLowerCase().includes(query);
    const potrivitGen = !genActiv ||
      (film.genre_names || []).includes(genActiv);
    return potriviteCautare && potrivitGen;
  });
  numarAfisat = 0;
  afiseazaGrilaFilme();
}

function afiseazaGrilaFilme() {
  grilaFilme.innerHTML = '';

  if (filmeFiltrate.length === 0) {
    grilaFilme.innerHTML = `<div class="gol"><div class="icon-gol">◎</div><p>Niciun film găsit.</p></div>`;
    butonMaiMulte.style.display = 'none';
    return;
  }

  const deAfisat = filmeFiltrate.slice(0, numarAfisat + MARIME_PAGINA);
  numarAfisat    = deAfisat.length;
  deAfisat.forEach(film => grilaFilme.appendChild(creeazaCard(film)));
  butonMaiMulte.style.display = numarAfisat < filmeFiltrate.length ? 'block' : 'none';
}

butonMaiMulte.addEventListener('click', () => {
  const urmatoarele = filmeFiltrate.slice(numarAfisat, numarAfisat + MARIME_PAGINA);
  urmatoarele.forEach(film => grilaFilme.appendChild(creeazaCard(film)));
  numarAfisat += urmatoarele.length;
  butonMaiMulte.style.display = numarAfisat < filmeFiltrate.length ? 'block' : 'none';
});


function creeazaCard(film) {
  const card   = document.createElement('div');
  card.className    = 'card-film';
  card.dataset.id   = film.id;

  const inLista = esteInLista(film.id);
  const an      = film.release_date ? film.release_date.slice(0,4) : '';
  const gen     = (film.genre_names || [])[0] || '';
  const rating  = film.vote_average ? film.vote_average.toFixed(1) : '—';

  card.innerHTML = `
    ${inLista ? '<div class="insigna-lista">✓ Lista mea</div>' : ''}
    ${film.poster_path
      ? `<img class="poza-film" src="${TMDB_IMG}w300${film.poster_path}" alt="${film.title}" loading="lazy"/>`
      : `<div class="fara-poza">🎬</div>`}
    <div class="info-card">
      <div class="titlu-card">${film.title}</div>
      <div class="an-card">${an}</div>
      ${gen ? `<div class="gen-card">${gen}</div>` : ''}
      <div class="rating-card"><span>★</span> ${rating}</div>
    </div>`;

  card.addEventListener('click', () => deschideModal(film.id));
  return card;
}

function afiseazaLista() {
  grilaLista.innerHTML = '';
  const lista  = luaLista();

  if (lista.length === 0) {
    grilaLista.innerHTML = `<div class="gol"><div class="icon-gol">◎</div><p>Lista ta e goală.<br/>Adaugă filme din secțiunea Descoperă!</p></div>`;
    return;
  }

  const filme = toateFilmele.filter(f => lista.includes(f.id));
  filme.forEach(film => grilaLista.appendChild(creeazaCard(film)));
}

async function incarcaRecomandari() {
  const lista = luaLista();

  if (lista.length === 0) {
    golRec.style.display    = 'flex';
    grilaRec.style.display  = 'none';
    return;
  }

  golRec.style.display   = 'none';
  grilaRec.style.display = 'grid';
  grilaRec.innerHTML     = `<div class="incarcare"><div id="roata"></div><p>Se calculează recomandările...</p></div>`;

  try {
    const raspuns = await fetch(`${API}/recomandari`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ lista })
    });
    const date = await raspuns.json();

    grilaRec.innerHTML = '';
    if (!date.recomandari || date.recomandari.length === 0) {
      grilaRec.innerHTML = `<div class="gol"><div class="icon-gol">✦</div><p>Nu am găsit recomandări.</p></div>`;
      return;
    }

    date.recomandari.forEach(film => grilaRec.appendChild(creeazaCard(film)));
  } catch(e) {
    grilaRec.innerHTML = `<div class="gol"><div class="icon-gol">⚠</div><p>Eroare la calculul recomandărilor.</p></div>`;
  }
}


async function deschideModal(filmId) {
  filmModalCurent = filmId;
  modal.classList.remove('ascuns');
  document.body.style.overflow = 'hidden';


  document.getElementById('backdrop').style.backgroundImage = 'none';
  document.getElementById('poster').style.display = 'none';
  document.getElementById('titlu-modal').textContent = 'Se încarcă...';
  document.getElementById('taguri').innerHTML   = '';
  document.getElementById('meta').innerHTML     = '';
  document.getElementById('descriere').textContent = '';
  document.getElementById('distributie').innerHTML = '';
  actualizeazaButonLista();

  try {
    const raspuns = await fetch(`${API}/film/${filmId}`);
    const date    = await raspuns.json();
    umpleModal(date.detalii, date.distributie);
  } catch(e) {
    const film = toateFilmele.find(f => f.id === filmId);
    if (film) umpleModalSimplu(film);
  }
}

function umpleModal(detalii, distributie) {

  const backdropEl = document.getElementById('backdrop');
  backdropEl.style.backgroundImage = detalii.backdrop_path
    ? `url(${TMDB_IMG}w1280${detalii.backdrop_path})`
    : 'none';


  const posterEl = document.getElementById('poster');
  if (detalii.poster_path) {
    posterEl.src            = `${TMDB_IMG}w342${detalii.poster_path}`;
    posterEl.style.display  = 'block';
  }

  document.getElementById('taguri').innerHTML = (detalii.genres || [])
    .map(g => `<span class="tag-gen">${g.name}</span>`).join('');


  document.getElementById('titlu-modal').textContent = detalii.title || '';

  const an      = detalii.release_date ? detalii.release_date.slice(0,4) : '';
  const durata  = detalii.runtime ? `${detalii.runtime} min` : '';
  const rating  = detalii.vote_average ? detalii.vote_average.toFixed(1) : '';
  document.getElementById('meta').innerHTML = `
    ${an     ? `<span>📅 ${an}</span>`                               : ''}
    ${durata ? `<span>⏱ ${durata}</span>`                           : ''}
    ${rating ? `<span><span class="auriu">★</span> ${rating}</span>` : ''}`;


  document.getElementById('descriere').textContent = detalii.overview || 'Nicio descriere disponibilă.';

  const actori = (distributie.cast || []).slice(0, 6);
  if (actori.length) {
    document.getElementById('distributie').innerHTML = `
      <div class="titlu-distributie">Distribuție</div>
      <div class="lista-actori">
        ${actori.map(a => `
          <div class="chip-actor">
            ${a.profile_path
              ? `<img class="poza-actor" src="${TMDB_IMG}w45${a.profile_path}" alt="${a.name}"/>`
              : `<div class="poza-actor" style="background:var(--fundal);display:flex;align-items:center;justify-content:center;font-size:11px;color:var(--text3)">◎</div>`}
            <span>${a.name}</span>
          </div>`).join('')}
      </div>`;
  }

  actualizeazaButonLista();
}

function umpleModalSimplu(film) {
  const posterEl = document.getElementById('poster');
  if (film.poster_path) {
    posterEl.src           = `${TMDB_IMG}w342${film.poster_path}`;
    posterEl.style.display = 'block';
  }
  document.getElementById('taguri').innerHTML =
    (film.genre_names||[]).map(g=>`<span class="tag-gen">${g}</span>`).join('');
  document.getElementById('titlu-modal').textContent = film.title;
  document.getElementById('meta').innerHTML =
    film.release_date ? `<span>📅 ${film.release_date.slice(0,4)}</span>` : '';
  document.getElementById('descriere').textContent = film.overview || '';
  actualizeazaButonLista();
}

function actualizeazaButonLista() {
  const inLista = esteInLista(filmModalCurent);
  butonLista.textContent  = inLista ? '✓ În lista mea — Elimină' : '+ Adaugă în lista mea';
  butonLista.className    = inLista ? 'salvat' : '';
}

butonLista.addEventListener('click', () => {
  toggleLista(filmModalCurent);
  actualizeazaButonLista();
  reimprospataChard(grilaFilme, filmModalCurent);
  reimprospataChard(grilaLista, filmModalCurent);
  reimprospataChard(grilaRec, filmModalCurent);
  const grilaNLP = document.getElementById('grila-cautare-nlp');
  if (grilaNLP) reimprospataChard(grilaNLP, filmModalCurent);
});

function reimprospataChard(grila, filmId) {
  const carduri = grila.querySelectorAll(`.card-film[data-id="${filmId}"]`);
  carduri.forEach(card => {
    const film = toateFilmele.find(f => f.id === filmId);
    if (film) 
      card.replaceWith(creeazaCard(film));
  });
}

function inchideModal() {
  modal.classList.add('ascuns');
  document.body.style.overflow = '';
  filmModalCurent = null;
  const sectiuneActiva = document.querySelector('.sectiune.activa');
  if (sectiuneActiva?.id === 'lista')       
    afiseazaLista();
  if (sectiuneActiva?.id === 'recomandari') 
    incarcaRecomandari();
}

butonInchide.addEventListener('click', inchideModal);
modal.addEventListener('click', e => { if (e.target === modal) inchideModal(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') inchideModal(); });

// ── CAUTARE NLP ──
const inputNLP       = document.getElementById('input-nlp');
const butonCautaNLP  = document.getElementById('buton-cauta-nlp');
const grilaCautareNLP= document.getElementById('grila-cautare-nlp');
const infoNLP        = document.getElementById('rezultate-nlp-info');

butonCautaNLP.addEventListener('click', cautareNLP);
inputNLP.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    cautareNLP();
  }
});

async function cautareNLP() {
  const text = inputNLP.value.trim();
  if (!text) return;

  butonCautaNLP.disabled = true;
  butonCautaNLP.textContent = 'Se caută...';
  grilaCautareNLP.innerHTML = `<div class="incarcare"><div id="roata"></div><p>Se analizează descrierea cu TF-IDF...</p></div>`;
  infoNLP.classList.add('ascuns');

  try {
    const raspuns = await fetch(`${API}/cauta`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ text })
    });
    const date = await raspuns.json();

    grilaCautareNLP.innerHTML = '';

    if (!date.rezultate || date.rezultate.length === 0) {
      grilaCautareNLP.innerHTML = `<div class="gol"><div class="icon-gol">◎</div><p>Niciun film găsit pentru descrierea ta.<br/>Încearcă o altă formulare.</p></div>`;
      infoNLP.classList.add('ascuns');
    } else {
      infoNLP.classList.remove('ascuns');
      infoNLP.innerHTML = `
        <span>🔍 Rezultate pentru: <span class="nlp-query-text">"${text}"</span></span>
        <span class="nlp-count">${date.rezultate.length} filme găsite</span>`;
      date.rezultate.forEach(film => grilaCautareNLP.appendChild(creeazaCard(film)));
    }
  } catch(e) {
    grilaCautareNLP.innerHTML = `<div class="gol"><div class="icon-gol">⚠</div><p>Eroare la căutare. Verifică dacă serverul Flask rulează.</p></div>`;
    infoNLP.classList.add('ascuns');
  }

  butonCautaNLP.disabled = false;
  butonCautaNLP.textContent = 'Caută';
}
