# Analisi OpenAI: consenso e budget

Il backend locale usa Responses API. Codex resta lo strumento di sviluppo: non viene usata l'autenticazione Codex per chiamare l'API fotografica.

## Flusso

1. Salvare la chiave nella configurazione OpenAI della web app. Il backend la conserva nel portachiavi macOS; non viene restituita al frontend, inserita nei log o scritta nel repository.
2. Scegliere la modalità ibrida: il passaggio locale è facoltativo. Selezionare le anteprime da valutare, partendo dalla proposta locale oppure da tutte le anteprime importate. Il confronto riguarda soltanto il campione confermato, non le foto escluse dall’invio.
3. Impostare il numero finale OpenAI, indipendente dalla quantità locale. Richiedere la stima senza dover impostare un budget: questa operazione non chiama OpenAI e non invia immagini. Un budget complessivo rimane facoltativo. La conferma autorizza il limite prudenziale del singolo piano mostrato.
4. Rivedere elenco e anteprime, modello, testo originale, numero finale, stima, limite prudenziale e consumo precedente.
5. Confermare esplicitamente l'invio. Soltanto questa azione abilita le richieste del piano mostrato. Una modifica a dati, criteri, modello o revisione richiede una nuova stima e una nuova conferma.

Il testo delle istruzioni è un elemento `input_text` utente separato, identico al testo salvato (Unicode, righe e spazi inclusi). L’interfaccia offre un unico testo modificabile. I criteri dei vecchi servizi/preset sono riportati visibilmente in questo campo, mantenendo il testo originale come prefisso; soltanto un salvataggio esplicito consolida i campi. Gli schemi tecnici e le categorie derivate non sostituiscono il testo salvato. Si inviano soltanto le anteprime selezionate: mai RAW, catalogo, percorsi degli originali o credenziali nel prompt. Le anteprime possono comunque contenere dati personali visibili, per questo l'elenco richiede conferma. `store:false` disabilita la conservazione della risposta per il successivo recupero tramite API; non è una promessa di assenza di tutti i log di servizio OpenAI.

## Stima

Modelli verificati il 18 novembre 2026: GPT-5.4 mini (`gpt-5.4-mini-2026-03-17`, input 0,75 USD/output 4,50 USD per milione di token) e GPT-5.4 (`gpt-5.4-2026-03-05`, input 2,50 USD/output 15 USD per milione). Nessuno sconto cache è presunto nella stima prudenziale. Le tariffe hanno una finestra di validità: quando scadono, il codice richiede una verifica prima di nuove conferme.

La riserva considera il limite di output, un limite prudenziale per input testuale/immagine e un margine aggiuntivo. Non è una misurazione della qualità né una promessa di costo esatto. Il consumo token restituito da OpenAI viene registrato; il costo è calcolato con le tariffe del piano e non sostituisce la fattura. Il limite è applicativo, non un limite configurato nell'account OpenAI.

## Interruzioni e ripresa

Una richiesta alla volta, nessun tentativo automatico illimitato. Prima dell'invio viene riservato il costo prudenziale; il budget include consumi e riserve delle prove precedenti dello stesso servizio. Timeout o esito incerto mantengono la riserva: non vengono trattati come chiamate gratuite. Annullare interrompe le chiamate successive, ma non può ritirare una richiesta già partita.

I risultati validi vengono riutilizzati soltanto quando anteprima, testo/criteri, modello e versione del formato coincidono. Riprendere richiede una nuova stima e conferma; il riavvio del backend non riparte automaticamente con invii cloud. Si può continuare con il motore locale. Risultati incompleti o mancata corrispondenza non comportano riempimenti con foto non pertinenti.

I risultati API sono proposte di revisione, non modifiche a Lightroom. Decisioni manuali, stelle già esistenti e originali restano protetti dal flusso separato delle stelle.

## Crediti

Non viene presunto un saldo o un accredito nominale. Il budget locale è distinto dai crediti e dalle condizioni dell'account. Non si acquistano crediti e non si attivano ricariche automatiche. Controllare credito e scadenza nel proprio account prima della prova: le condizioni attuali possono dipendere dall'abbonamento e dal ciclo di fatturazione.

## Fonti ufficiali

- Modello/tariffe: https://developers.openai.com/api/docs/models/gpt-5.4-mini
- Immagini e costo token: https://developers.openai.com/api/docs/guides/images-vision
- Output strutturato: https://developers.openai.com/api/docs/guides/structured-outputs
- Crediti ChatGPT/API: https://developers.openai.com/api/docs/guides/chatgpt-api-credits

## Aggiornamento dei modelli

«Verifica modelli disponibili» legge `/v1/models` con la chiave salvata, senza inviare fotografie. La lista viene conservata localmente, mostra la data di verifica e segnala dopo 24 ore che occorre aggiornarla. I nuovi modelli restituiti dall’account compaiono anche se non ancora verificati; rimangono disabilitati per l’analisi finché compatibilità e tariffa non sono validate nel registro applicativo. Il modello scelto non viene sostituito automaticamente. Cambiare chiave invalida la disponibilità memorizzata.

La disponibilità dell’account non certifica il supporto immagini o il prezzo: il registro verificato è distinto dall’elenco dinamico. Tariffe e capacità non vengono inventate dal nome del modello.

Ulteriore fonte: https://developers.openai.com/api/docs/models/gpt-5.4

## Quantità finale e selezione complessiva

Il numero finale API è separato dall’obiettivo locale. Dopo un’analisi completata si può ricomporre la proposta con un altro numero riutilizzando le valutazioni conservate, senza inviare nuove richieste. Non può recuperare informazioni sulle immagini mai incluse nel campione confermato.

Priorità: istruzioni dell’utente, copertura delle categorie richieste e varietà della serie, poi qualità tra alternative pertinenti. La qualità non può sostituire una categoria richiesta con un’altra. Le categorie sono interpretazioni del modello, non fatti certificati: mancanze o incertezze vengono segnalate e non riempite con immagini non pertinenti.

Tra alternative pertinenti contano espressione, gesto, composizione e significato nella serie: nitidezza e perfezione tecnica non sono il criterio dominante. Il merito visivo stimato dal modello resta un giudizio ordinale soggettivo, non una misura calibrata della bellezza. Le preferenze esplicite dell’utente hanno precedenza.

## Confronto dell’insieme

Il piano API comprende: interpretazione testuale delle categorie, valutazione delle singole anteprime, confronto globale tramite provini JPEG indicizzati (16 immagini per foglio) e tutte le valutazioni del campione. Ogni richiesta mantiene il testo originale utente come elemento separato identico. Il riepilogo include anche le richieste di interpretazione e confronto globale nel costo. Non vengono aggiunte fotografie fuori dall’elenco confermato.

Il confronto globale restituisce un ordinamento completo delle corrispondenze confermate. La ricomposizione locale conserva decisioni manuali e almeno una rappresentante per ogni categoria riconosciuta e idonea. I dettagli piccoli nei provini restano incerti e il riconoscimento non equivale a una garanzia di copertura. Un confronto mancante/invalido non viene spacciato per completato.

Il motore locale valuta tutte le anteprime e combina le evidenze dell’intero servizio con categorie, scene indicative e diversità degli embedding. Non mostra contemporaneamente tutte le fotografie al VLM locale: il confronto globale locale è basato sulle evidenze aggregate e sui vettori visivi. Le vecchie cache senza categorie vengono invalidate dalla versione del motore.
