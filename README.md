# LrC Photo Selection

Prima selezione fotografica locale per Lightroom Classic, con priorità alla copertura del servizio. Interfaccia in italiano, nessun hosting e nessuna trasmissione cloud automatica.

**La sola modifica consentita in Lightroom è assegnare una stella alle candidate idonee.** Nessuna raccolta, nessun flag o metadato aggiuntivo, nessuna modifica allo sviluppo. Originali e sidecar non vengono aperti per la scrittura, spostati o cancellati. Prima delle stelle è obbligatorio verificare manualmente che Lightroom abbia disabilitata la scrittura automatica dei metadati.

## Stato reale

- Implementati servizi persistenti con aggiunta di foto e archivio locale, revisione manuale con annulla/ripristina, sostituzione delle alternative, preset versionati e piani stelle confermati con ricevute.
- Confronto con scorrimento collegato, risoluzione anteprima, scorciatoie e ordine cronologico con offset fotocamera. Il comando «Mostra le candidate» seleziona temporaneamente le foto in Lightroom senza aggiungere metadati.
- Motore iniziale funzionante e prudente: raggruppa soltanto anteprime JPEG identiche. Non riconosce ancora persone, scene o pose; non promette una riduzione a 500.
- Analisi locale esplicita con Apple Vision compilato e SigLIP 2 opzionale configurato: cache riprendibile, ritagli dei volti e suggerimenti di confronto. Non influenza le esclusioni; nessun modello scaricato automaticamente. SigLIP non ancora provato su fotografie reali.
- Passaggio OpenAI disponibile con selezione del campione, stima, budget per servizio e conferma esplicita prima di ogni piano di invio; collaudato con trasporto simulato, non ancora con richieste reali. Nessuna chiave API necessaria per il flusso locale.
- Test automatici con dati sintetici; verifica reale Lightroom ancora da eseguire sul catalogo di prova indicato dall'utente. Il catalogo principale non autorizzato non viene usato nei test; non esiste un blocco per anno nel prodotto.

## Installazione sul Mac

Richiede Python 3.11+ e Node.js compatibile con Vite. Ambiente di sviluppo verificato: Apple M1 Max / 64 GB, macOS 26.6.2, Python 3.13 e Node 26. Lightroom installato: 16.0 (integrazione reale da collaudare).

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pip install -e . --no-deps
cd web
npm ci
npm run build
cd ..
.venv/bin/lrc-selection
```

In alternativa, dopo l'installazione, aprire `scripts/start.command`. Il backend ascolta solo `http://127.0.0.1:8765`; non apre Lightroom né cataloghi automaticamente.

In un secondo terminale ottenere il token di connessione locale:

```sh
.venv/bin/lrc-selection --show-connection
```

Il token non è una chiave API OpenAI. Inserirlo nella pagina locale e nella configurazione del plugin; non condividerlo. I dati sono in `~/Library/Application Support/LrC Photo Selection/`, fuori dal repository.

## Uso

1. Installare `plugin/lrc-photo-selection.lrplugin` da Gestione plug-in di Lightroom e configurare la connessione.
2. Per i primi test aprire esclusivamente un catalogo ad hoc o vecchio concordato; selezionare esplicitamente le foto. Non usare il catalogo principale non autorizzato.
3. “Prepara servizio” permette di creare un servizio oppure aggiungere la selezione a uno esistente dello stesso catalogo. Importa solo nuove foto, preservando decisioni e valutazioni iniziali; non avvia analisi. Dopo un’aggiunta eseguire nuovamente la selezione prima di preparare stelle.
4. Nella web app scegliere quantità e criteri, quindi avviare la selezione oppure effettuare la revisione manuale.
5. Confrontare, escludere o bloccare candidate; annullare/ripristinare decisioni nella web app. Preparare e **confermare l’elenco esatto** delle stelle. Archiviare un servizio lo conserva e ne sospende le modifiche finché viene riaperto.
6. “Mostra le candidate in Lightroom” seleziona temporaneamente le foto visibili nelle sorgenti/filtri attivi e segnala eventuali assenze. Da “Applica stelle” applicare il piano dopo la verifica manuale XMP e la conferma dell’elenco. Foto già valutate, modificate nel frattempo o dubbie vengono saltate. Le esclusioni successive non rimuovono stelle.

La quantità è un obiettivo minimo automatico tra 1 e il totale importato. Copertura e incertezza possono produrre più candidate. Decisioni manuali possono rendere il target impossibile: vengono preservate e il conflitto segnalato.

## Verifiche

```sh
.venv/bin/python -m pytest -q
cd web
npm test
npm run build
```

I test Lua richiedono `lupa` (presente nell'ambiente di sviluppo). Nessun test automatico deve aprire cataloghi o fotografie dell'utente. Per la prova reale vedere [procedura Lightroom](docs/lightroom-test.md).

## Analisi locale opzionale

La baseline non richiede modelli. Gli adattatori aggiuntivi leggono esclusivamente anteprime di un servizio già importato:

```sh
.venv/bin/python -m pip install -e '.[local-ai]'
mkdir -p .build
swiftc native/FaceDetection.swift -o .build/lrc-face-detection
.venv/bin/python -m lrc_selection.features --data-dir '/percorso/dati/app' --service-id ID --vision-tool .build/lrc-face-detection
# Opzionale: aggiungere --siglip-dir /percorso/checkpoint-verificato
```

Se il helper Vision è compilato, la web app offre “Analizza dettagli locali”. Per un helper in altra posizione impostare `LRC_VISION_TOOL`; per SigLIP configurare `LRC_SIGLIP_DIR` prima di avviare il backend (richiede dipendenze `local-ai`). Il rilevamento viene avviato soltanto con il comando esplicito. La cache resta nella directory dati dell’app.

I pesi devono essere già presenti localmente: l'adattatore non li scarica. Le evidenze salvate sono separate dalle decisioni e non vengono presentate come riconoscimento affidabile delle persone. La procedura e le licenze sono in [modelli](docs/models.md).

Il benchmark confronta la proposta con annotazioni manuali JSON e non apre le foto:

```sh
.venv/bin/python scripts/benchmark.py --data-dir '/percorso/dati/app' --labels '/percorso/annotazioni.json'
```

Vedere [requisiti](docs/requirements.md), [architettura](docs/architecture.md) e [protocollo](shared/README.md). Non includere fotografie, cataloghi, credenziali, pesi o dati personali nei commit.

Risultati e limiti del collaudo: [verifica 0.1.0](docs/validation.md).

## Verifiche aggiuntive

`node scripts/browser_smoke.mjs` verifica il flusso con Chrome headless, backend su porta 18765, dati sintetici e ricevute SDK simulate. Richiede Chrome installato e asset web compilati; non apre Lightroom. `scripts/benchmark_scale.py` misura il backend su 1.000 e 5.000 elementi sintetici.

Vedere [audit e piano](docs/audit-plan.md). Le raccolte Classic locali facoltative restano una fase successiva al collaudo SDK; questa versione non crea o modifica raccolte. Annulla/ripristina riguarda le decisioni manuali, non le stelle applicate o le analisi già eseguite.

### Modello locale per istruzioni libere

Sul Mac Apple Silicon: installare `.venv/bin/pip install -e '.[local-instructions]'`, poi eseguire `.venv/bin/python scripts/setup_local_model.py`. È un download esplicito di pesi, senza inviare foto; richiede diversi GB di spazio. Il backend rileva il modello nello spazio dati dell’app. Per riprodurre il runtime del collaudo usare requirements-local-ai-lock.txt.

Scegli un preset per copiare i suoi criteri e modificarli nel servizio, oppure parti senza preset e scrivi direttamente le istruzioni. L’analisi restituisce una proposta da rivedere. Confermarla modifica soltanto la selezione locale; le stelle richiedono ancora il piano e la conferma separata in Lightroom.

La sezione OpenAI salva la chiave nel portachiavi e permette di scegliere il modello da una lista aggiornabile dall’account. Il flusso ibrido richiede stima e conferma esplicita del campione e del budget; non invia automaticamente foto. Istruzioni originali preservate, consumi e riserve persistenti, ripresa con nuova conferma. Dettagli in [docs/openai.md](docs/openai.md).
