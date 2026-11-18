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
- `GET /api/services/{id}/rating-plan/latest`: rifiuta piani obsoleti.
- `POST /api/services/{id}/rating-plan/claim`: riserva il piano e blocca le modifiche web fino alla ricevuta completa.
- `POST /api/services/{id}/rating-receipts`: esiti per piano, retry identico idempotente.

Le sole target_rating consentite dal produttore di piani sono 1, per baseline 0. Il plugin deve validare di nuovo ogni item: non fidarsi ciecamente di un JSON ricevuto. Catalogo e foto si identificano con ID, mai con il nome file. Ricevute non contengono originali, cataloghi o segreti.
