# Contratto v1

La fonte eseguibile dei contratti è `backend/lrc_selection/models.py`; OpenAPI viene esposta dal backend. Gli scambi plugin usano `schema_version: 1`.

- `POST /api/imports`: manifest servizio completo; retry identico idempotente.
- `PUT /api/services/{id}/photos/{photo_id}/preview`: corpo JPEG; token Bearer.
- `POST /api/services/{id}/complete`: chiude importazione.
- `GET /api/services` e `GET /api/services/{id}`: riepilogo e stato.
- `PUT /api/services/{id}/settings`: revisione attesa + snapshot impostazioni.
- `PATCH /api/services/{id}/decisions/{photo_id}`: revisione, stato, blocco; `confirm_last` esplicito per ultima candidata.
- `POST /api/services/{id}/analyze`: avvio esplicito, revisione attesa.
- `POST /api/services/{id}/rating-plan`: prepara elenco verificabile, non applica stelle.
- `POST /api/services/{id}/rating-plan/confirm`: `{batch_id}` conferma l’elenco esatto visto dall’utente.
- `GET /api/services/{id}/rating-plan/latest`: restituisce il piano attivo, altrimenti quello confermato; mai l’ultimo piano arbitrario. Rifiuta piani obsoleti.
- `POST /api/services/{id}/rating-plan/claim`: riserva il piano e blocca le modifiche web fino alla ricevuta completa.
- `POST /api/services/{id}/rating-receipts`: esiti per piano, retry identico idempotente.

Le sole target_rating consentite dal produttore di piani sono 1, per baseline 0. Il plugin deve validare di nuovo ogni item: non fidarsi ciecamente di un JSON ricevuto. Catalogo e foto si identificano con ID, mai con il nome file. Ricevute non contengono originali, cataloghi o segreti.

## Estensioni additive v1

- `POST /api/services/{id}/append`: `{schema_version:1,id:<UUID operazione>,catalog_id,photos:[Photo]}`; restituisce `{photo_ids,completed}`. Stesso catalogo obbligatorio, retry identico idempotente, identità in conflitto rifiutata. Foto esistenti ignorate senza aggiornare il baseline.
- `POST /api/services/{id}/complete`: per un’aggiunta richiede `{import_id}`; il primo import mantiene il body opzionale. L’aggiunta invalida i piani e richiede analisi esplicita; il target resta invariato.
- `PUT /api/services/{id}/archive`: `{revision,archived}`. Archiviazione solo a operazioni concluse; nessuna cancellazione dei dati.
- `POST /api/services/{id}/replace`: `{revision,from_photo_id,to_photo_id}`; candidata e alternativa nello stesso gruppo, entrambe sbloccate, modifica atomica.
- `POST /api/services/{id}/undo` e `/redo`: `{revision}`. Cronologia persistente delle decisioni; i dettagli espongono `can_undo` e `can_redo`. Non annulla modifiche Lightroom.
- `GET /api/capabilities`: disponibilità dei componenti locali (`features`, `faces`, `siglip`), senza percorsi privati.
- `POST /api/services/{id}/features`: `{revision}`, avvio esplicito dell’estrazione dei componenti locali configurati. Usa il medesimo stato job; nessun download o richiesta cloud.

Aggiornare backend, web app e plugin insieme: i nuovi plugin richiedono la conferma esplicita del piano. `PRAGMA user_version=1` riguarda solo SQLite dell’app; l’aggiornamento è additivo, non riscrive i servizi esistenti. I campi mancanti di archivio e cronologia assumono i valori iniziali. I digest dei manifest v1 esistenti sono preservati.
