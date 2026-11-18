# Prova in Lightroom Classic

La prima verifica usa il catalogo vecchio JPEG autorizzato dall’utente, aprendo il file con doppio clic nel Finder. Il catalogo principale non autorizzato è escluso da queste prove. Il plugin non impone blocchi per nome o anno del catalogo.

1. Aprire soltanto il catalogo di prova concordato. In **File → Gestione plug-in**, aggiungere `plugin/lrc-photo-selection.lrplugin`.
2. Avviare il backend locale; in **Libreria → Extra plug-in → Configura connessione locale** inserire il token locale.
3. Selezionare un piccolo campione concordato e usare **Prepara servizio**. Confrontare anteprime e identificativi, includendo una copia virtuale se disponibile. Senza originali online, la disponibilità dipende dalle anteprime restituite da Lightroom. Non cercare o ricollegare originali. Un’importazione sospesa si riprende mantenendo la stessa selezione.
4. Annotare rating, sviluppo, flag e raccolte iniziali; quando disponibili nel campione autorizzato, rilevare checksum di originali e sidecar. Nella web app provare selezione, confronto, esclusione e blocco; preparare e confermare l’elenco esatto del piano stelle.
5. In **Impostazioni catalogo → Metadati** controllare **Scrivi automaticamente modifiche in XMP**. Provare prima annullamento e conferma XMP non selezionata: nessuna stella deve cambiare. Per la prova positiva l’impostazione deve essere disabilitata; il plugin non la modifica. Se attiva e non autorizzata la modifica manuale, interrompere il test di scrittura.
6. **Applica stelle** mostra catalogo, servizio, identificativo del piano e lista esatta delle modifiche. Confrontare gli esiti: solo i passaggi autorizzati da 0 a 1 sono ammessi. Foto escluse, già valutate o modificate dopo l’importazione devono restare invariate. Sviluppo, flag e raccolte devono coincidere col baseline.
7. Ripetere l’operazione e verificare l’assenza di nuove modifiche. Modificare manualmente un rating già applicato e verificare che una nuova importazione della stessa foto lo preservi. Il servizio non è applicabile a un altro catalogo.

Il journal locale è scritto prima della mutazione SDK e protegge i tentativi interrotti. In caso di esito incerto controllare il rating nel catalogo: non viene riapplicato automaticamente. Ripetere **Applica stelle** per inviare una ricevuta rimasta in sospeso.

## Stato della verifica
Il controllo grafico del Mac ha restituito `cgWindowNotFound`, impedendo il doppio clic richiesto. Lightroom non è stato aperto dall’agente. Nessun catalogo è stato letto direttamente e nessuna valutazione reale è stata applicata. I test Lua con SDK simulato non sostituiscono questa prova.

## Casi aggiunti dopo audit

- Aggiungere altre foto allo stesso servizio, comprese foto già importate e nomi duplicati. Verificare solo nuove anteprime, stesso target e decisioni intatte; provare interruzione e ripresa della stessa selezione.
- Preparare due piani, confermarne uno e interrompere l’applicazione: la ripresa deve recuperare quello attivo. Annullare durante l’attesa di accesso al catalogo e verificare nessun rating per la foto non ancora iniziata.
- “Mostra le candidate” deve selezionare gli identificativi corretti senza scrivere metadati o raccolte. Con filtri o sorgenti che nascondono candidate deve segnalare la selezione parziale.
- La raccolta locale facoltativa non è implementata: prima servirà verificare sul vero SDK che la creazione non abiliti sincronizzazione.
- Il controllo grafico è stato ritentato dopo l’audit: Finder continua a rispondere `cgWindowNotFound`. Nessun catalogo aperto e nessuna prova reale dichiarata completata.
