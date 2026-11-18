# Requisiti e decisioni

Applicazione personale per la prima selezione dei servizi fotografici. Il primo preset è Matrimonio; quantità e criteri sono scelti prima di premere Avvia selezione. Il target è tra 1 e tutte le foto importate: la proposta automatica non deve scendere sotto il target e può superarlo per conservare copertura. Una decisione manuale può rendere il target impossibile: segnalare, mai annullarla.

## Vincoli
La sola modifica Lightroom consentita è il rating in stelle. Non creare raccolte, metadati plugin, flag o etichette. Nessun intervento su originali, sviluppo o sidecar. SDK ufficiale; nessun accesso SQL al catalogo. Anteprime temporanee separate. Stelle soltanto dopo verifica esplicita di scrittura automatica metadati disabilitata e revisione delle modifiche. Catalogo esistente intatto.

## Flusso
Selezione Lightroom → titolo → anteprime e identità catalogo/foto/copia virtuale → servizio locale → configurazione criteri e quantità → avvio esplicito → candidate e alternative → revisione manuale → anteprima rating → applicazione SDK e ricevuta. Nessuna analisi parte durante l'importazione.

## Copertura
Distinguere momento, scena, composizione delle persone, posa/azione e raffica. Foto isolate, momenti unici mossi, cambi di persone, risate vs pose serie e rilevamenti incerti non vanno eliminati per qualità tecnica. Ogni alternativa deve avere rappresentante, evidenza e possibilità di recupero. Gruppi individuati non implicano che tutte le situazioni reali siano state riconosciute.

## Configurazione
Preset modificabili e creabili, con copia versionata per servizio; impostazioni correnti non alterano servizi precedenti. Istruzioni libere rese verificabili, con stato supportato/ambiguo/non supportato. Offset per fotocamera solo nell'app. Modalità locale senza rete dopo installazione; modalità ibrida opzionale e mai implicita.

## Dati
Separare metadati importati, inferenze/versioni dei modelli, regole/preset, proposte automatiche, decisioni manuali e rating applicati. Blocchi manuali prevalgono sulle nuove analisi. Ripresa e revisione persistenti; niente motivazioni inventate. Dati sintetici esplicitamente separati.

## API
Solo anteprime strettamente necessarie; persone riconosciute localmente. Chiave nel Portachiavi, mai in frontend/Git/log. Stima e budget per servizio, contabilizzazione richieste già avviate, tentativi/concorrenza limitati, cache, interruzione prudente e ripresa. Nessun acquisto/ricarica. I crediti Pro dichiarati dall'utente non sono saldo verificato; condizioni e prezzi vanno verificati alla configurazione.

## Accettazione
Prima preservare situazioni significative, composizioni e immagini uniche, poi ridurre doppioni, tempo e costo. Il primo traguardo è il flusso manuale completo, seguito da motore locale verificato su campione reale concordato e da prova API con budget autorizzato. Nessuna fotografia dell'utente accessibile prima della scelta del campione.
