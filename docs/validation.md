# Verifica dell’implementazione

## Aggiornamento dopo audit — 18 novembre 2026

- **47 test backend/SDK simulati passati**, inclusi i 15 test Lua; **13 test React passati**; build TypeScript/Vite riuscita.
- Regressioni: piani A/B e ripresa dopo riavvio, conferma esatta, annullamento durante attesa del write gate, riuso ricevuta esistente, import incrementale idempotente, catalogo errato e identità in conflitto, protezione baseline/decisioni/target, cronologia persistente e sostituzione atomica, compatibilità digest manifest v1, archivio e riapertura.
- Analisi locale esplicita e cache verificate con encoder/detector sintetici: ripresa dopo interruzione, invalidazione per versione del modello, errore di rilevamento non memorizzato. NumPy installato nel venv per il test dei vicini visivi; nessun peso IA scaricato.
- Prova integrata `scripts/browser_smoke.mjs` con Chrome headless e backend HTTP reale: decisione, annulla/ripristina, analisi Apple Vision su anteprime uniformi sintetiche, confronto e risoluzione, piano confermato, claim e ricevuta SDK simulata, aggiunta foto, archivio e riapertura. Nessuna stella reale applicata. Desktop 1500 px e mobile 390 px senza overflow.
- `scripts/benchmark_scale.py`, rilevazione prima dell’integrazione finale: 1.000 elementi, dettaglio circa 16 ms, baseline 0,087 s; 5.000 elementi, dettaglio circa 63 ms, baseline 1,002 s. Tutte le candidate conservate. Solo metadati e una preview sintetica per servizio; non è un benchmark RAW, IA o del rendering di migliaia di miniature.
- Ritentato accesso Finder: `cgWindowNotFound`. **Collaudo reale Lightroom non eseguito.** Restano da verificare `lastEditTime`, disponibilità delle anteprime JPEG senza originali, comportamento della selezione con filtri e semantica SDK reale.
- La raccolta locale facoltativa è rinviata fino a tale collaudo; nessuna creazione o sincronizzazione di raccolte presente nel codice. Nessun modello semantico calibrato sul campione reale, nessuna API OpenAI avviata.

Annulla/ripristina agisce sulle decisioni manuali; non annulla le analisi o le stelle Lightroom. Le garanzie di serializzazione dei test riguardano le normali operazioni SDK del plugin e i controlli nel write gate, non un’esecuzione arbitraria di più processi indipendenti sullo stesso catalogo.

## Verifica iniziale 0.1.0 (storico)

## Eseguito sul Mac

- Backend/API e simulazione SDK Lua 5.1: **32 test passati** (`.venv/bin/python -m pytest -q`).
- Componenti React in DOM simulato: **7 test passati** (`npm --prefix web test`).
- Build TypeScript/Vite completata; controllo dipendenze Python superato.
- Prova HTTP con server reale su loopback e sei anteprime sintetiche: asset compilati, autenticazione cookie, importazione, selezione conservativa (5 candidate per target 3) e piano di 4 rating idonei verificati. Server temporaneo arrestato dopo la prova.
- Apple Vision compilato con Swift e provato su un'immagine sintetica uniforme: nessun volto rilevato, nessun errore.
- Nessuna fotografia personale utilizzata nei test. Nessun catalogo letto tramite SQL o modificato direttamente.

I test coprono importazione idempotente, nomi duplicati, copie virtuali nel manifest, revisione concorrente, preset immutabili per servizio, target e copertura prudente, decisioni manuali, budget di spazio disco, ripresa, token e origine delle richieste, claim esclusivo delle stelle, journal prima della mutazione, conservazione rating e timestamp, annullamento e ricevute.

## Limiti aperti

La prova SDK reale su Lightroom Classic 16.0 è bloccata da `cgWindowNotFound` nella sessione grafica. Non è stato aperto Lightroom. Il campione autorizzato è il catalogo vecchio JPEG con le sue anteprime; il catalogo principale non autorizzato è escluso dal collaudo. Non dichiarare la compatibilità Lightroom reale come già certificata.

Verificare in particolare il comportamento di `lastEditTime` dopo una modifica manuale 0 → 3 → 0 stelle: i test simulati validano il confronto, non provano la semantica del campo Adobe. Se Lightroom non segnala questo cambiamento, il confronto non può rilevare quella sequenza e la procedura di importazione/applicazione va rivista prima dell'uso operativo.

La registrazione distingue cataloghi per percorso e fotografie per UUID + localIdentifier. Non distingue automaticamente la sostituzione del file catalogo allo stesso percorso con una copia che conserva gli stessi identificativi: in quel caso non riutilizzare servizi precedenti e registrare nuovamente il catalogo.

Il journal locale con flush/close e rinomina protegge dalle interruzioni del processo; non è una garanzia contro guasti hardware o perdita di alimentazione prima della persistenza fisica del filesystem.

La baseline confronta JPEG identici e conserva tutto il resto. Non sono calibrati modelli semantici, riconoscimento persone, scene, occhi chiusi, pose o punteggi estetici. SigLIP 2 non è stato scaricato né eseguito. Le evidenze opzionali non influenzano automaticamente le esclusioni. Offset temporali usati dall’ordinamento cronologico della web app; non sono evidenza di equivalenza nel motore.

Modalità OpenAI non implementata/abilitata per l'analisi: mancano campione misurato, scelta modello, configurazione Keychain, stima e budget autorizzato. Nessuna richiesta API o spesa è stata effettuata.

## Audit dipendenze web

`npm audit --omit=dev`: **0 vulnerabilità**. L'audit completo segnala la catena di strumenti di sviluppo basata su picomatch (ReDoS, GHSA-fc5q-39xc-vjpf), senza correzione pubblicata nella fonte consultata il 18 novembre 2026. Non adottare automaticamente il downgrade suggerito dall'audit. Il prodotto serve solo asset statici dal backend Python: Vite/Vitest e i glob di build non ricevono input dell'utente né sono esposti come servizio dell'app. Rivalutare l'advisory prima di aggiornare gli strumenti o esporre un dev server.

Fonte: https://github.com/advisories/GHSA-fc5q-39xc-vjpf

Un avviso di deprecazione Starlette riguarda il test client httpx; i test passano. Nessun errore di esecuzione rilevato nei controlli svolti.

## Revisione dell’interfaccia

Layout a pagina unica con provino principale, strumenti laterali, palette neutra chiara e barra superiore scura. Slider quantità sincronizzato con inserimento numerico preciso; slider separato per la dimensione delle anteprime. I dettagli dei criteri restano espandibili e i limiti del motore sono visibili.

Verificati build e 7 test React, compresi sincronizzazione slider/campo, limiti della quantità e assenza di avvio implicito. Acquisito screenshot reale con Chrome headless autorizzato e sei anteprime sintetiche; controllo desktop a 1500 px e mobile a 390 px senza overflow orizzontale. Nessun catalogo o fotografia reale coinvolto.

## Aggiornamento SDK reale — 18 novembre 2026

Il proprietario ha aperto e autorizzato `catalogo-di-prova.lrcat`, cartella cartella del campione autorizzato. Installazione e connessione riuscite; primo import bloccato da `os.rename` assente nel runtime Adobe, corretto con API SDK e test di persistenza. Dettagli e limiti aggiornati in `lightroom-test.md`. Le precedenti note sul blocco `cgWindowNotFound` descrivono i tentativi iniziali: ora il controllo funziona parzialmente, con timeout sui dialoghi. Il flusso reale completo e l’applicazione delle stelle restano da verificare.

## Istruzioni libere e preset — collaudo 18 novembre 2026

- 100 test backend passati nella sandbox; test Apple Vision separato su fixture sintetica passato fuori sandbox (101 complessivi). 18 test frontend e build passati. Browser smoke sintetico desktop/mobile passato senza overflow a 390 px.
- Qwen3-VL 4B MLX eseguito offline sulle 160 anteprime autorizzate di Campione di prova. Richiesta di benchmark «uccelli», senza criteri Matrimonio, target 7: 70 yes, 62 no, 28 uncertain, circa 463 secondi prima del riordinamento per diversità. Questi sono giudizi del modello, non etichette manuali di verità.
- Riordinamento dei yes tramite SigLIP: circa 7 secondi. Ispezionato il provino delle 7 proposte: tutte mostrano uccelli, con soggetti a terra e in volo. Non misurati recall globale, qualità comparativa, errori nelle 28 incerte o copertura delle situazioni.
- Controllo negativo su due anteprime: «Seleziona solo fotografie di elefanti» restituisce zero proposte e avviso di nessuna corrispondenza rilevata; nessun riempimento forzato. Non costituisce una verifica dell’assenza su tutte le 160 foto.
- Benchmark separato: le impostazioni e decisioni del servizio reale non sono state sostituite, nessuna stella applicata. Per riprodurlo usare scripts/benchmark_instructions.py con un servizio autorizzato. Report completi e immagini restano solo nello spazio dati locale escluso da Git.
- Il runtime registra hash e versioni per cache/ripresa. I test verificano testo originale integro in valutazioni locali e payload OpenAI, criteri ambigui, preferenze, casi non pertinenti e manuali. Non è una promessa di interpretazione corretta di qualsiasi testo.
- OpenAI: configurazione chiave/modello e payload implementati e testati senza rete. Keychain nativo non collaudato con chiave reale. Trasporto di analisi, stima/budget/consumi e prova API reale restano da completare; nessuna spesa.

## Flusso OpenAI — aggiornamento 18 novembre 2026

Trasporto Responses, stima, budget persistente per servizio, conferma del campione, testo originale, cancellazione/ripresa, cache e ricevute implementati. Le precedenti note «non abilitato» descrivono lo stato iniziale e sono superate. 118 test backend passati (escluso il test Apple Vision già verificato nella sessione precedente). Quindici test specifici coprono il runner API, tre il catalogo modelli. Tutti i trasporti OpenAI sono simulati: nessuna foto reale inviata e nessuna spesa API effettuata. Keychain e disponibilità dei modelli con una chiave reale restano da collaudare.

Frontend: 26 test passati e build produzione riuscita. Verifica sul backend riavviato: catalogo locale modelli disponibile, servizio reale senza job API, consumi e riserve a zero. Nessuna richiesta di aggiornamento modelli eseguita sull’account reale.

Smoke browser API completo (`scripts/api_browser_smoke.mjs`): stima senza chiamate, conferma obbligatoria, testo Unicode/spazi identico, una chiamata simulata per due anteprime identiche tramite cache, consumo registrato e riserva rilasciata. Screenshot desktop prima/dopo e mobile verificati, nessun overflow a 390 px. Fixture separata, chiave falsa e trasporto sostituito prima dell’avvio del server; nessuna rete OpenAI.

## Revisione della selezione complessiva e del flusso — 18 novembre 2026

134 test backend passati (Apple Vision invariato escluso), 32 test frontend passati, build produzione e diff check riusciti. Verificati copertura uccelli/ritratti con risposte sintetiche, prevalenza delle decisioni manuali, invalidazione delle vecchie cache, testo unico/preset, avvisi obsoleti, API diretta, stima senza budget obbligatorio, confronto globale, ranking invalido, riserve/costi, ripresa, vecchi piani rifiutati e numero finale modificabile senza chiamate.

Entrambi gli smoke browser sono passati con sole fixture sintetiche. Il flusso API ha eseguito tre richieste simulate: interpretazione, una valutazione riutilizzata per due anteprime identiche, confronto globale. Stima senza trasporto, consenso esplicito, testo originale intatto e ricomposizione 1→2 senza nuove richieste. Screenshot desktop/mobile ispezionati.

Backend riavviato senza analisi attive; verifica in sola lettura del servizio reale: nessun invio, consumo o riserva API. La precisione del nuovo riconoscimento di categorie e del confronto globale su Campione di prova resta da verificare con la prova manuale dell’utente. I risultati precedenti non sono stati ricalcolati automaticamente. Per usare la nuova logica locale avviare una nuova analisi; per OpenAI ricalcolare la stima, poiché i piani precedenti non comprendono il confronto globale.

## 2026-11-18 — Risposte locali incomplete e scorrimento

Diagnosi in sola lettura del test autorizzato Campione di prova: 150 risposte non valide su 160, 8 non corrispondenti e 2 corrispondenti. La precedente pipeline dichiarava comunque completata la proposta. Una categoria conteneva inoltre il segnaposto letterale del prompt invece dei tre soggetti richiesti. La causa precisa degli output non validi non è dimostrabile senza gli output grezzi, che non erano conservati.

Prompt locale v6: schema compatto, massimo 1024 token, categorie validate durante il tentativo di riparazione, rifiuto dei segnaposto. Cache precedente invalidata tramite versione. Le risposte incomplete impediscono una nuova proposta e mantengono le decisioni; la vecchia proposta è segnalata come obsoleta. Nessuna garanzia di qualità del modello deriva dai test sintetici. Il numero richiesto non giustifica inventare corrispondenze: una proposta incompleta richiede correzione/verifica.

Interfaccia: tutte le schede del filtro sono scorribili senza pulsante di caricamento; anteprime lazy per contenere il carico. Test: 140 backend superati (test Apple Vision escluso perché il processo helper non è disponibile nella sandbox), 34 frontend superati e build riuscita. Nessuna nuova inferenza reale o richiesta OpenAI eseguita durante questa correzione.

## Sostituzione locale autorizzata: Qwen3.5-9B

Il proprietario ha richiesto la sostituzione anche dopo aver ricevuto l'esito sintetico negativo sulla copertura (vedi docs/models.md). Installati MLX-VLM 0.4.3 e miniaudio 1.73; pip check riuscito. Caricamento offline nel runtime definitivo verificato senza inferenza. Attivato Qwen3.5-9B-MLX-4bit mediante configurazione atomica; backend riavviato e capacità istruzioni verificata. Rimosso esclusivamente il precedente Qwen3-VL-4B dopo confronto della provenienza: 3.109.734.493 byte. SigLIP preservato perché componente distinto. Nessun servizio, decisione manuale, foto originale o valutazione Lightroom modificato; nessuna richiesta OpenAI. 144 test backend superati, uno Apple Vision escluso come nel controllo precedente.

## 19 novembre 2026 — Blocco prima della lettura delle fotografie

Diagnosi in sola lettura: 0 tentativi, 0 risposte non valide, 160 foto non valutate, 160 candidate ancora salvate. Il 9B aveva inventato ambiguità e limitazioni generiche interpretando l'elenco «uccelli, ritratti, landscape»; la pipeline aveva confuso blocco delle istruzioni e fallimento delle risposte visive.

Correzione v9: parser conservativo solo per elenchi di singole parole minuscole, senza operatori o criteri aggiuntivi; il resto resta affidato al modello. Originale preservato. Distinzione esplicita tra categorie alternative nella raccolta e compresenza richiesta nella stessa foto. Nessun criterio derivato viene aggiunto alle istruzioni effettive della valutazione visiva. Rimossi suggerimenti di soggetti non richiesti dal prompt generale. Contraddizioni e istruzioni non verificabili restano da chiarire; le risposte incoerenti vengono ritentate/respinte, non convertite artificialmente in corrispondenze. Cache invalidata dalla revisione v9.

I fallimenti ora indicano la causa e mantengono separati risultati parziali e interpretazioni precedenti. L'interfaccia mostra le candidate salvate anche quando il primo tentativo fallisce; corregge in lettura il vecchio messaggio «0 risposte non valide», senza riscrivere il servizio.

Verifica reale del modello su sole figure sintetiche: 11/11 controlli superati, 61,05 secondi, picco MLX circa 7,71 GB. Report [v9](benchmarks/local-model-9b-v9.json); i tentativi falliti v7/v8 restano tracciati. Riproducibile con scripts/check_local_model.py. Questi controlli non validano il merito fotografico o l'affidabilità generale delle istruzioni. Nessuna nuova analisi delle foto dell'utente, richiesta API o modifica di stelle.

## 19 novembre — Conservare risultati incerti e recuperare una lettura parziale

Ultimo tentativo Campione di prova: 160 immagini processate, 143 risposte positive, 14 negative, una incerta valida e due risposte non valide (schema/categorie). La precedente regola bloccava la proposta per quei due errori. Il proprietario ha precisato che gli esiti incerti devono essere inclusi.

Politica locale `retain-uncertain-v1`: proposta ordinaria con copertura delle categorie confermate, poi aggiunta di tutte le immagini incerte, con risposta non valida, anteprima mancante o valutazione non disponibile, salvo esclusioni/alternative manuali. Queste immagini hanno indicazione da rivedere e non provano copertura. La conservazione sopravvive al riordinamento SigLIP, può superare il target, e non cambia né i giudizi originali né la selezione API condivisa. Nessuna modifica a prompt/modelli o invalidazione delle risposte valide in cache. Errori per foto non bloccano più l'intero servizio; ambiguità bloccanti della richiesta e errori globali restano fallimenti espliciti.

L'accettazione manuale della proposta conserva lo stato da rivedere per queste immagini, senza sovrascrivere decisioni precedenti. Prima dell'accettazione rimane una proposta separata.

Recupero preparato dai 160 risultati salvati: 15 proposte ordinarie più 3 da rivedere, senza nuove inferenze, letture di immagini, chiamate API o stelle. Verificati revisione del servizio, testo originale, criteri, identità e hash delle anteprime nei metadati prima di scrivere. Il recupero usa la classifica per preferenze/scene già valutate, senza ricalcolare embedding.

Recupero applicato alla sola proposta locale (revisione 179 → 180): 18 proposte, di cui 3 da rivedere; decisioni e stelle non modificate. Verifica: 172 test backend superati (uno Apple Vision escluso), 36 frontend superati e build riuscita.

### 2026-11-19 — Connessione API HTTPS
Il runtime Python macOS non aveva CA nel contesto SSL predefinito (0 certificati):
handshake senza autenticazione verso api.openai.com fallito con verifica certificato,
riuscito TLS 1.3 con certifi. Analisi e discovery modelli usano ora esplicitamente
il bundle certifi, mantenendo verifica certificati e hostname. Errori API/rete
sono classificati con messaggi fissi, senza esporre risposte provider o segreti.
Nessuna nuova analisi cloud eseguita per questa verifica; la causa esatta del
precedente tentativo non è recuperabile dal vecchio messaggio generico. Riserve
precedenti conservate, senza inferire un addebito né avviare retry automatici.

### 2026-11-19 — Risposta fotografica API non utilizzabile
Nel tentativo reale sono rimaste salvate 15 valutazioni su 18. Il vecchio registro
non permette di distinguere rifiuto, risposta incompleta e violazione dello schema.
Ora questi esiti, quando il consumo è verificabile, conservano la foto come incerta
e consentono di proseguire con le altre richieste già confermate, senza retry.
Gli incerti restano nella proposta finale, salvo decisioni manuali di esclusione;
non attestano copertura delle categorie. Errori di rete, consumo non verificabile,
interpretazione o confronto globale continuano a sospendere il flusso.
Diagnostica sintetica salvata nelle ricevute, senza risposte grezze del provider.
Nessuna nuova chiamata cloud eseguita durante la correzione.
