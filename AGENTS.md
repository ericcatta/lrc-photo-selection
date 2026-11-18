# lrc-photo-selection

## Non-negotiable safety
- Lightroom is accessed exclusively through the official Lua SDK. Never read/write the catalog database directly.
- The only allowed Lightroom mutation is a photo's star rating, after an explicit preview and confirmation. No collections, flags, labels, keywords, plug-in metadata, or develop changes.
- Never delete, move, rename, overwrite, or modify original photos or their sidecars. Temporary previews/crops live only in application storage.
- Do not apply ratings while automatic metadata writing is enabled or its state is unverified. Do not change Lightroom preferences automatically or invoke saveMetadata.
- Preserve existing ratings and subsequent manual decisions. Repeated imports must not overwrite later manual work.
- Do not inspect user photos until a test sample is explicitly identified. Do not make cloud analysis requests until a sample and budget are explicitly authorized.
- No Sites, online hosting, telemetry, model downloads at import time, or secrets/photos/catalogs in Git.

## Product
Italian UI. Coverage before reduction. All images begin as candidates. Alternatives retain their representative and evidence. Uncertain groups preserve candidates. Requested quantity is an automatic minimum/target, never a hard cap: 1..imported image count. Manual decisions prevail; report infeasibility instead of changing them. Presets are versioned snapshots per service. Unsupported free-form criteria must be visible.

## Development
Backend Python/FastAPI/SQLite; frontend React/TypeScript; SDK Lua plug-in. Store runtime data under the user's Application Support, outside the repository. Separate imported facts, interpretations, settings, proposals, decisions, and rating receipts. All public exchange formats are versioned. Synthetic fixtures must be clearly labeled and never mixed with real services. Test behavior and safety invariants. Report implemented vs actually verified.

## Orchestration preferences supplied by owner
Use Astra Medium as orchestrator when available. Personal agents: planner gpt-6.1-sol medium; grunt gpt-6-luna low; helper gpt-6-luna low. Delegate useful independent work, minimize redundant investigation, assign distinct ownership. If configured models are unavailable, explain and ask before substitution. No silent model changes.

## Aggiornamenti della sessione iniziale
- Il proprietario autorizza scegliere il modello disponibile più leggero/economico adeguato al compito; grunt gpt-6.1-sol disponibile è stato autorizzato in questa sessione.
- Per i test usare soltanto il catalogo JPEG autorizzato o dati sintetici. Non aprire né usare il catalogo principale non autorizzato. Nessun blocco per anno deve essere introdotto nel prodotto.
- Aprire Lightroom soltanto dal file del catalogo scelto (doppio clic richiesto dall'utente), mai avviandolo genericamente sull'ultimo catalogo.

## Audit approvato e implementazione
- Selezione temporanea delle candidate nella vista Lightroom consentita tramite SDK; non modifica metadati, raccolte o file.
- Raccolte Classic locali facoltative previste solo dopo collaudo reale SDK e verifica della mancata sincronizzazione; attualmente non implementate. Nessun flag/etichetta aggiuntivo.
- Servizi e archivio web restano locali; aggiunte solo nello stesso catalogo, senza aggiornare baseline o decisioni delle foto già importate.
- Piani stelle confermati esplicitamente nella web app e nuovamente nel plugin. Riprendere il piano attivo, non un piano più recente arbitrario.
- I test browser usano solo fixture sintetiche; Chrome headless è stato autorizzato dal proprietario. Il controllo grafico continua a essere bloccato da cgWindowNotFound.

## Campione autorizzato per il collaudo reale
- Il 18 novembre 2026 il proprietario ha aperto personalmente `catalogo-di-prova.lrcat` e autorizzato il test sulla cartella selezionata mostrata nello screenshot. Questa autorizzazione amplia quella precedente per JPEG; non autorizza altre cartelle o il catalogo principale non autorizzato.
- Installazione del plugin locale e collegamento al backend con token nel portachiavi esplicitamente confermati. Stelle sempre subordinate a riepilogo e verifica XMP.

## Istruzioni e preset aggiornati
- Selezionare un preset compila automaticamente criteri e istruzioni, sempre modificabili nel servizio; aggiornamento e salvataggio come nuovo preset espliciti, snapshot precedenti immutabili. Nessun preset obbligatorio.
- Testo originale conservato integralmente, anche per le API; contesto tecnico separato, mai sostituzione con una riscrittura. Nessuna conferma obbligatoria dell’interpretazione: segnalare solo ambiguità, conflitti, assenza di corrispondenze o limiti effettivi.
- Qwen3-VL locale valutato sul campione autorizzato; shortlist rivedibile distinta dalla copertura conservativa. Accettazione locale annullabile e piano stelle separato. Non presentare i risultati dei modelli come fatti o correttezza universale.
