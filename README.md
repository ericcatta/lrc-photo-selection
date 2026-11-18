# LrC Photo Selection

Prima selezione fotografica locale per Lightroom Classic, con priorità alla copertura del servizio. Interfaccia in italiano, nessun hosting e nessuna trasmissione cloud automatica.

**La sola modifica consentita in Lightroom è assegnare una stella alle candidate idonee.** Nessuna raccolta, nessun flag o metadato aggiuntivo, nessuna modifica allo sviluppo. Originali e sidecar non vengono aperti per la scrittura, spostati o cancellati. Prima delle stelle è obbligatorio verificare manualmente che Lightroom abbia disabilitata la scrittura automatica dei metadati.

## Stato reale

- Implementati backend persistente, revisione manuale, preset versionati, controlli di concorrenza e piani di rating con ricevute.
- Motore iniziale funzionante e prudente: raggruppa soltanto anteprime JPEG identiche. Non riconosce ancora persone, scene o pose; non promette una riduzione a 500.
- Adattatori offline SigLIP 2 e Apple Vision disponibili separatamente; non usati per escludere foto senza calibrazione. Nessun modello scaricato automaticamente.
- Passaggio OpenAI **non abilitato**: richiede campione, modello, condizioni dei crediti e budget concordati. Nessuna chiave API necessaria per il flusso locale.
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
3. “Prepara servizio” importa metadati e anteprime, senza avviare analisi e senza modificare foto o catalogo.
4. Nella web app scegliere quantità e criteri, quindi avviare la selezione oppure effettuare la revisione manuale.
5. Confrontare, escludere o bloccare candidate; preparare il riepilogo delle stelle.
6. Dal plugin applicare il piano dopo la verifica manuale XMP e la conferma. Foto già valutate, modificate nel frattempo o dubbie vengono saltate. Le esclusioni successive non rimuovono stelle.

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

I pesi devono essere già presenti localmente: l'adattatore non li scarica. Le evidenze salvate sono separate dalle decisioni e non vengono presentate come riconoscimento affidabile delle persone. La procedura e le licenze sono in [modelli](docs/models.md).

Il benchmark confronta la proposta con annotazioni manuali JSON e non apre le foto:

```sh
.venv/bin/python scripts/benchmark.py --data-dir '/percorso/dati/app' --labels '/percorso/annotazioni.json'
```

Vedere [requisiti](docs/requirements.md), [architettura](docs/architecture.md) e [protocollo](shared/README.md). Non includere fotografie, cataloghi, credenziali, pesi o dati personali nei commit.

Risultati e limiti del collaudo: [verifica 0.1.0](docs/validation.md).
