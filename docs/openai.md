# Analisi OpenAI: consenso e budget

Il backend locale usa Responses API. Codex resta lo strumento di sviluppo: non viene usata l'autenticazione Codex per chiamare l'API fotografica.

## Flusso

1. Salvare la chiave nella configurazione OpenAI della web app. Il backend la conserva nel portachiavi macOS; non viene restituita al frontend, inserita nei log o scritta nel repository.
2. Eseguire il primo passaggio locale. Passare alla modalità ibrida e scegliere esplicitamente le anteprime del campione da valutare. È possibile includere alternative per rivalutarle.
3. Impostare il budget totale in USD per questo servizio. Richiedere la stima: questa operazione non chiama OpenAI e non invia immagini.
4. Rivedere elenco e anteprime, modello, testo originale, criteri aggiuntivi, costo prudenziale, consumo precedente e budget disponibile.
5. Confermare esplicitamente l'invio. Soltanto questa azione abilita le richieste del piano mostrato. Una modifica a dati, criteri, modello o revisione richiede una nuova stima e una nuova conferma.

Il testo delle istruzioni è un elemento `input_text` utente separato, identico al testo salvato (Unicode, righe e spazi inclusi). I criteri aggiuntivi e lo schema tecnico non lo sostituiscono. Si inviano soltanto le anteprime selezionate: mai RAW, catalogo, percorsi degli originali o credenziali nel prompt. Le anteprime possono comunque contenere dati personali visibili, per questo l'elenco richiede conferma. `store:false` disabilita la conservazione della risposta per il successivo recupero tramite API; non è una promessa di assenza di tutti i log di servizio OpenAI.

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
