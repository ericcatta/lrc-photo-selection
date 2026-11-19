# Guida locale Lightroom

La fonte dei contenuti è `docs/workflow-guide.json`. Dopo una modifica eseguire
`python3 scripts/generate_workflow_guide.py`; `--check` verifica che le copie Lua
e web siano aggiornate. Non modificare manualmente `GuideData.lua` o
`web/src/guide-data.json`.

La voce «Guida — da Lightroom alla selezione e ritorno» e i pulsanti Guida nei
dialoghi Prepara servizio e Applica stelle usano soltanto il SDK per le viste.
La guida non richiede backend, connessione, token o catalogo aperto.

L’applicazione stelle ha un binding `actionBinding.enabled` alla casella di
attestazione XMP, oltre a un controllo difensivo che restituisce un messaggio
comprensibile senza riservare il piano sul backend né applicare stelle. Le modifiche restano bloccate
finché l’utente non attesta la verifica. Il plugin non cambia preferenze XMP.

Verifica automatica: simulazione Lua 5.1 per guida offline, coerenza delle copie,
nomi dei comandi effettivi, blocco XMP, esiti completi e parziali. Il rendering e il
binding nativo devono essere collaudati manualmente in Lightroom dopo Reload
Plug-in; le simulazioni non sostituiscono tale controllo.

Riferimento SDK: `LrDialogs.presentModalDialog`, `actionBinding` e
`viewFactory:push_button` nella documentazione Adobe Lightroom SDK
([copia della reference](https://lrc.mcor.dev/modules/LrDialogs.html)).
