# Prova in Lightroom Classic

Il campione iniziale era il catalogo vecchio JPEG. Il 18 novembre 2026 il proprietario ha aperto personalmente `catalogo-di-prova.lrcat` e autorizzato la cartella cartella del campione autorizzato (161 foto totali, 160 visibili al momento della selezione). Il catalogo principale non autorizzato è escluso da queste prove. Il plugin non impone blocchi per nome o anno del catalogo.

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

## Collaudo reale del 18 novembre 2026 — in corso

Plugin installato e attivo; collegamento al backend locale confermato dal proprietario con apertura della web app. Il token locale viene individuato dal plugin e salvato nel portachiavi solo dopo conferma.

Il primo comando Prepara servizio si è fermato nella registrazione locale: `os.rename` non è disponibile nel runtime SDK. Corretto usando `LrFileUtils.move`, con file pending/previous e recupero dello stato precedentemente confermato. Il solo temporaneo di registrazione prodotto dal tentativo fallito è stato validato per il catalogo autorizzato e recuperato; nessun file del catalogo o fotografia è stato modificato. Plugin ricaricato dalla Gestione plug-in.

Verifica automatica: 63 test backend passati nella sandbox; il test Apple Vision su immagine sintetica fallisce nella sandbox ma passa separatamente fuori dalla sandbox (64 casi complessivi). Comprende simulazioni di guasti dello storage eseguendo Common.lua reale con `os.rename` assente.

Importazione reale ancora da riprovare: il controllo grafico restituisce timeout durante la chiusura della Gestione plug-in. Nessuna stella applicata; stato XMP non ancora verificato, ritorno delle stelle non collaudato.

### Importazione ricevuta

Il secondo tentativo ha trasferito 160/160 anteprime con 160 identificativi distinti, ma il completamento ha restituito 422: il plugin inviava `{}` mentre il backend richiede `null` per un nuovo servizio. Corretto Prepare.lua e aggiunto test che esegue Lua reale e verifica il payload contro FastAPI. Il servizio «Servizio di prova» è stato completato tramite API locale ed è `ready`; questa ripresa manuale non certifica ancora il completamento end-to-end dal plugin corretto. Nessuna decisione manuale o stella applicata. La cartella indicava 161 foto totali, ma la selezione autorizzata e trasmessa conteneva 160 foto visibili.
