# Architettura e sicurezza

## Componenti
Il plugin SDK Lua legge solo le foto esplicitamente selezionate, genera JPEG e invia un manifest JSON v1 al backend FastAPI su 127.0.0.1:8765. React/TypeScript è compilato e servito dallo stesso backend. SQLite è esclusivamente il database dell'app: non si apre il database Lightroom.

Dati runtime: `~/Library/Application Support/LrC Photo Selection/`, permessi privati. Il plugin conserva il token nel portachiavi SDK e registrazione/journal in file locali fuori dal catalogo. Token locale distinto da qualsiasi chiave OpenAI; autenticazione Bearer del plugin, cookie HttpOnly SameSite Strict del browser. Validazione Host e Origin, niente CORS permissivo. Access log HTTP disabilitato. Nessuna telemetria.

## Identità e revisioni
Ogni servizio ha UUID, ID catalogo registrato nei file locali del plugin, UUID foto e localIdentifier SDK. Il nome file non è una chiave. Copie virtuali mantengono identità propria. Un catalogo copiato/spostato non viene ricollegato automaticamente. Le mutazioni web richiedono revisione attesa; il manifest ritrasmesso è idempotente e deve corrispondere integralmente.

Importazione separata: manifest, anteprime, completamento. Le anteprime hanno nomi derivati da hash degli ID; mai utilizzare percorsi originali per scrivere. Il backend valida i JPEG e non apre gli originali. Un errore anteprima è visibile, non una prova di equivalenza.

## Separazione dei dati
Ogni servizio conserva compartimenti distinti: photos (fatti importati immutabili), settings e preset_snapshot, proposal (interpretazione automatica versionata), decisions (manuali), job e receipts (operazioni riportate dal plugin). Transazioni SQLite serializzano modifiche e preparazione dei piani. Gli esiti di analisi vengono scartati se la revisione è cambiata. Interruzioni ripristinano stato riprendibile senza cancellare decisioni.

## Stelle
Il backend prepara un piano immutabile, confermato esplicitamente nella web app; solo il plugin può eseguire quel piano tramite SDK. La ripresa recupera il piano attivo anche se erano stati preparati altri piani. Il dialogo SDK mostra identificativi, nomi e operazioni esatte. Baseline 0 stelle, edit time noto, identità e catalogo corrispondenti, nessun tentativo precedente, confronto aggiornato dentro il write gate. Rating preesistenti, modifiche successive e casi dubbi vengono saltati. Il journal locale protegge anche da crash tra modifica e ricevuta. Nessuna rimozione automatica di stelle se una candidata viene successivamente esclusa.

L'auto-write XMP non ha un getter pubblico SDK verificato. Prima di ogni applicazione l'utente deve controllare nelle impostazioni Lightroom che la scrittura automatica sia disabilitata. Se non può verificarlo, non si applicano stelle. Il plugin non cambia preferenze e non chiama salvataggi metadati. Questa conferma manuale è una precondizione operativa, non una verifica automatica dell'impostazione.

## Limiti espliciti
Il primo motore raggruppa soltanto JPEG derivati identici byte per byte. Non afferma di riconoscere scene, persone o pose. Anche le anteprime identiche non dimostrano identità degli originali ad alta risoluzione. Le istruzioni libere vengono ora valutate dal modello visivo locale Qwen3-VL quando installato; in assenza del modello l’analisi con istruzioni è bloccata. La modalità ibrida non invia richieste finché campione, modello, configurazione e budget non sono autorizzati e verificati.

Il catalogo principale non autorizzato è escluso dai test del team, non dall'uso del prodotto. Nessuna regola nel plugin blocca cataloghi per anno.

## Estensioni dopo audit

Gli import incrementali hanno un ID operazione proprio e vengono chiusi con quello stesso ID. Solo le nuove foto vengono aggiunte; fatti importati e decisioni preesistenti non sono sostituiti. Una proposta precedente resta consultabile come obsoleta, con le nuove foto candidate; è obbligatoria un’analisi esplicita prima delle stelle.

La cronologia salva prima/dopo delle singole decisioni o sostituzioni atomiche e un cursore persistente. Una nuova decisione dopo Annulla apre un nuovo ramo e scarta la possibilità di ripristinare il vecchio ramo. Non è una cronologia delle analisi: annullare un override può lasciare lo stesso risultato se la proposta automatica lo produce indipendentemente. Nessuna operazione di cronologia modifica Lightroom.

La presentazione calcola rappresentanti e avvisi dalla selezione effettiva. L’archivio è locale e reversibile; non elimina anteprime o originali. I dettagli locali usano una cache separata per componente, checksum anteprima e versione. Vedere audit-plan.md per protocollo e limiti.

## Selezione guidata dal testo

Il preset è una sorgente opzionale: scegliendolo si copiano istruzioni e criteri nella configurazione modificabile del servizio. Aggiornare/salvare un preset non cambia i servizi precedenti. Il testo originale viene conservato integralmente e passato a ogni valutazione visiva; una sintesi interna non lo sostituisce e non richiede un passaggio aggiuntivo dell’utente.

Qwen3-VL 4B quantizzato usa MLX sul Mac. Ogni anteprima riceve una valutazione strutturata yes/no/uncertain e motivazione, con preferenze ordinali e scene ipotizzate. Ambiguità e criteri non verificabili producono avvisi; non sono interpretati come criteri soddisfatti. Il modello non certifica identità, equivalenza o copertura. Le valutazioni incerte/non pertinenti non riempiono il numero richiesto. La diversità per etichette di scena è euristica, non riconoscimento affidabile delle situazioni.

La shortlist è una proposta da rivedere, distinta dalle candidate conservative. Solo «Usa questa proposta», dopo avviso di copertura, registra decisioni annullabili nel servizio: nessuna mutazione Lightroom. Le decisioni manuali preesistenti prevalgono. Il piano stelle è un passaggio ulteriore e continua a consentire solo 0→1.

La configurazione OpenAI espone chiave (portachiavi nativo) e modello. Il costruttore Responses conserva il testo originale come contenuto utente distinto dalle istruzioni tecniche e imposta store=false. Il trasporto di analisi cloud, il budget e il registro consumi non sono ancora abilitati: salvare la configurazione non invia foto.
