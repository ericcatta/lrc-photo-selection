# LrC Photo Selection

**Una prima selezione ragionata delle fotografie, da rifinire in Lightroom Classic.**

**Edizione italiana** · [🇬🇧 English edition — interfaccia, plugin e documentazione in inglese](https://github.com/ericcatta/lrc-photo-selection-en)

LrC Photo Selection collega un plugin Lightroom a una web app che funziona sul Mac. Parti dalle foto di un servizio, descrivi cosa vuoi conservare e rivedi una proposta prima di riportarla in Lightroom attraverso le stelle. L’interfaccia e la guida sono in italiano.

L’obiettivo non è scegliere soltanto le immagini più nitide: contano le tue istruzioni, la varietà delle situazioni e il valore fotografico. Un’espressione, una composizione o un momento significativo possono prevalere sulla perfezione tecnica.

> Il progetto è una prima versione funzionante, in evoluzione. Le proposte dei modelli richiedono revisione: non sono una garanzia di riconoscimento corretto di persone, soggetti o situazioni.

## Cosa puoi fare

- Scrivere **istruzioni libere in un unico campo**, partire da un preset modificabile e salvare nuovi preset. Il testo originale viene mantenuto, anche negli invii OpenAI.
- Scegliere **Solo locale**, **Locale + OpenAI** oppure **Direttamente OpenAI**. Non serve una chiave API per usare il percorso locale.
- Impostare la quantità per ogni servizio. La quantità locale e quella finale OpenAI sono separate.
- Rivedere il provino, aprire una foto in grande, navigare tra le anteprime, confrontare due foto e includere o escludere manualmente le immagini. Sono disponibili blocco delle decisioni, annulla/ripristina e filtri.
- Dare priorità a **situazioni distinte**: prima una rappresentante per situazione, poi ulteriori varianti distribuite tra i gruppi. La bellezza fotografica e le istruzioni precedono la sola nitidezza.
- Conservare le immagini incerte come **da rivedere**. Se servono 23 foto per rappresentare le situazioni disponibili e ne hai chieste 20, la proposta può superare il numero. Le decisioni manuali prevalgono.
- Usare OpenAI soltanto dopo aver visto campione, modello, valutazioni nuove o riutilizzabili e costo stimato, quando disponibile. Il confronto riguarda **il campione confermato**, non automaticamente tutte le foto importate.
- Salvare servizi locali, aggiungere nuove foto allo stesso servizio e archiviare i lavori conclusi senza cancellarli.

## Cosa cambia in Lightroom

**L’unica modifica ai dati delle fotografie è assegnare una stella alle candidate idonee che hanno zero stelle**, dopo anteprima dell’elenco e conferma nella web app e nel plugin.

Le stelle già presenti non vengono abbassate o rimosse. Escludere una foto nella web app non cancella il file e non toglie stelle. Il plugin non modifica sviluppo, flag, etichette, parole chiave o raccolte; non sposta, rinomina o elimina originali e sidecar.

Il comando **Mostra le candidate in Lightroom** cambia soltanto la selezione temporanea nella vista. L’accesso a Lightroom avviene tramite SDK ufficiale, senza leggere o scrivere direttamente il database del catalogo.

## Installazione più semplice sul Mac

Non è ancora un’app distribuita con installer: serve scaricare questo progetto e preparare l’ambiente locale una volta. Il percorso principale è **macOS con Lightroom Classic**. Per il modello locale MLX serve un Mac **Apple Silicon**; altri sistemi non hanno lo stesso livello di collaudo.

### 1. Prepara Python e Node.js

Installa, se non sono già presenti:

- **Python 3.11 o successivo**, dal [sito Python](https://www.python.org/downloads/macos/).
- **Node.js con npm**, dal [sito Node.js](https://nodejs.org/en/download). La build richiede Node 20.19 o successivo nella serie 20, oppure Node 22.12 o successivo.
- **Lightroom Classic**. Il plugin dichiara SDK minimo 12; le verifiche reali sono state eseguite con Lightroom Classic 16 su Mac.

Dopo l’installazione riapri Terminale. Puoi controllare le versioni con:

```sh
python3 --version
node --version
npm --version
```

### 2. Scarica e installa il progetto

Su GitHub scegli **Code → Download ZIP**, estrai il contenuto e sposta la cartella in una posizione stabile. In alternativa:

```sh
git clone https://github.com/ericcatta/lrc-photo-selection.git
cd lrc-photo-selection
```

Apri la cartella `scripts` e fai doppio clic su **`install.command`**. Lo script verifica i requisiti, crea `.venv` nella cartella del progetto, installa le dipendenze Python e compila la web app. Richiede una connessione Internet per scaricare le dipendenze.

Se macOS non apre il file con un doppio clic, eseguilo da Terminale dalla cartella del progetto:

```sh
zsh scripts/install.command
```

L’installazione non scarica modelli, non apre Lightroom e non invia fotografie. Per installare manualmente gli stessi componenti:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
npm --prefix web ci
npm --prefix web run build
```

### 3. Avvia la web app locale

Fai doppio clic su **`scripts/start.command`** e lascia aperta la finestra Terminale. In alternativa, dalla cartella del progetto:

```sh
.venv/bin/lrc-selection
```

Il backend ascolta soltanto su **http://127.0.0.1:8765**. Non apre automaticamente Lightroom o un catalogo. Per fermarlo premi **Ctrl+C** nella sua finestra Terminale.

### 4. Aggiungi il plugin a Lightroom

1. Apri il catalogo Lightroom nel quale vuoi lavorare.
2. Apri **File → Gestione plug-in** e premi **Aggiungi**.
3. Scegli la cartella **`plugin/lrc-photo-selection.lrplugin`** dentro il progetto scaricato e chiudi Gestione plug-in. Mantieni il progetto in quella posizione.
4. Con il backend avviato, apri **Libreria → Extra plug-in → Configura connessione locale**.
5. Se compare **Connessione locale rilevata**, premi **Collega**. Il plugin conserva il token nel portachiavi Lightroom e apre la web app.

Se la connessione non viene rilevata, ottieni il token in un secondo Terminale, dalla cartella del progetto:

```sh
.venv/bin/lrc-selection --show-connection
```

Incollalo nel dialogo di connessione del plugin. **Il token locale non è la chiave API OpenAI**: serve a collegare la web app e il plugin sul tuo computer. Non pubblicarlo o condividerlo.

La guida completa è disponibile da **Libreria → Extra plug-in → Guida — da Lightroom alla selezione e ritorno**, dai pulsanti **Guida** del plugin e dalla web app. La guida Lightroom funziona anche quando il backend è spento.

## Scegli come analizzare le foto

### Solo locale

L’installazione di base permette di preparare i servizi, rivederli manualmente e usare il motore prudente basato sulle anteprime identiche. **Per interpretare le istruzioni libere localmente occorre installare e attivare il modello visivo.** Non viene scaricato quando importi le foto.

Sul Mac Apple Silicon, dalla cartella del progetto:

```sh
.venv/bin/python -m pip install -e '.[local-instructions]'
.venv/bin/python scripts/setup_local_model.py --model Qwen3.5-9B-MLX-4bit --activate
```

Il secondo comando è un **download esplicito di pesi da Hugging Face**, richiede diversi GB di spazio e non invia fotografie. Riavvia il backend dopo la configurazione. Il modello richiede memoria e risorse locali: non è garantita una velocità o una qualità uniforme su ogni Mac. La versione delle istruzioni locale e il nuovo raggruppamento sono verificati con casi sintetici; la qualità sul proprio tipo di servizio va valutata su un campione.

Senza questo componente puoi usare la revisione manuale oppure il percorso diretto OpenAI. Dettagli, dipendenze e limiti dei modelli sono in [docs/models.md](docs/models.md).

### Locale + OpenAI oppure direttamente OpenAI

1. Nella web app apri **Impostazioni OpenAI → Configurazione OpenAI**.
2. Inserisci la tua **chiave API OpenAI** e salva. Viene conservata dal backend nel portachiavi macOS, non nel repository né nell’archiviazione del browser.
3. Premi **Verifica modelli disponibili** per aggiornare la lista del tuo account. Questa operazione non invia foto e non cambia automaticamente il modello selezionato.
4. Scegli un modello compatibile e salva la configurazione. La lista distingue compatibilità verificata o dedotta dalla famiglia e prezzi disponibili o sconosciuti.

Con un prezzo disponibile, il riepilogo mostra stima, riserva prudenziale e limite applicativo dell’invio; un budget cumulativo per servizio è facoltativo. **Una stima non è un costo garantito.**

I modelli compatibili senza tariffa disponibile restano selezionabili: il riepilogo dice chiaramente **Costo non disponibile** e richiede una conferma dell’invio senza stima né limite monetario verificabile. Un prezzo sconosciuto non viene presentato come zero. Il budget salvato non può limitare chiamate il cui costo non è calcolabile.

Il saldo e la fatturazione dell’account OpenAI non vengono verificati dall’app. Non vengono acquistati crediti o attivate ricariche. Codex è lo strumento con cui è sviluppato il progetto: **non sostituisce la chiave API del tuo account**. Per il protocollo completo vedere [docs/openai.md](docs/openai.md).

## Uso quotidiano: da Lightroom a Lightroom

La barra **Configura → Analizza → Rivedi → Lightroom → Esito** indica il prossimo passo. Consultare una fase non avvia analisi o invii.

1. **Prepara il servizio in Lightroom.** Seleziona le foto desiderate ed esegui **Libreria → Extra plug-in → Prepara servizio**. Scegli un nuovo servizio oppure aggiungi la selezione a uno esistente dello stesso catalogo. Attendi le anteprime: non vengono applicate stelle e non parte un’analisi.
2. **Configura nella web app.** Scrivi cosa vuoi conservare o scegli un preset e modifica il testo. Scegli percorso e quantità. Per esempio, “Conserva uccelli, ritratti e paesaggi, privilegiando momenti e composizioni differenti”. Puoi anche chiedere una selezione generale senza nominare soggetti specifici.
3. **Avvia l’analisi.** Nel percorso ibrido, dopo il locale puoi scegliere **Continua con OpenAI** oppure **Usa il risultato locale**. Il percorso diretto salta la selezione locale.
4. **Conferma l’eventuale invio OpenAI.** Rivedi campione, modello, testo, quantità e costi. Il riepilogo indica **Varietà valutata su X foto delle Y importate**. Nessuna foto viene inviata prima che tu spunti la conferma e premi **Conferma e invia a OpenAI**. Si inviano anteprime JPEG e provini derivati, non RAW o cataloghi.
5. **Rivedi la proposta.** Apri le anteprime in grande, confronta foto, usa **Includi/Escludi** e blocca le scelte da preservare. “Tutte le foto” permette di vedere anche quelle fuori dalla proposta. Gli incerti restano da rivedere. Conferma la selezione quando ti soddisfa: questa scelta non applica stelle.
6. **Prepara le stelle nella web app.** Apri **Rivedi le stelle**, prepara l’anteprima e conferma l’elenco. Dieci candidate possono richiedere soltanto quattro nuove stelle, se le altre sono già valutate. Nessuna stella preesistente viene abbassata.
7. **Applica da Lightroom.** In **Impostazioni catalogo → Metadati**, verifica che **Scrivi automaticamente le modifiche in file sidecar (XMP/ACR)** sia disattivato. Poi apri **Libreria → Extra plug-in → Applica stelle**, spunta l’attestazione di aver verificato XMP, controlla l’elenco e conferma. La casella nel plugin è un’attestazione: non cambia la preferenza di Lightroom.
8. **Controlla l’esito.** La web app mostra la ricevuta del plugin: stelle applicate, operazioni saltate e casi da verificare. Un esito parziale non è un successo completo. **Mostra le candidate in Lightroom** ti aiuta a ritrovare l’intera selezione senza creare raccolte.

Le situazioni e i gruppi sono valutazioni dei modelli, non identità o equivalenze certificate. La quantità è un obiettivo morbido: copertura, incerti e decisioni manuali possono richiedere più foto, mentre richieste senza corrispondenze o esclusioni manuali possono renderla irraggiungibile. La selezione non viene riempita nascondendo questa condizione.

## Se qualcosa si interrompe

| Situazione | Cosa fare |
| --- | --- |
| La pagina locale non si apre | Avvia `scripts/start.command`, lascia aperto Terminale e controlla l’indirizzo `127.0.0.1:8765`. |
| Il plugin non si collega | Avvia prima il backend; ripeti **Configura connessione locale** e, se serve, usa `--show-connection`. Non inserire qui la chiave OpenAI. |
| Le istruzioni locali non sono disponibili | Installa e attiva esplicitamente il modello locale, poi riavvia il backend; oppure scegli **Direttamente OpenAI**. |
| L’analisi API si interrompe | Usa **Prepara la ripresa** o l’azione di nuova stima indicata. Controlla valutazioni nuove e in cache prima di confermare. Le valutazioni valide si riutilizzano solo se campione, istruzioni, modello e formato sono compatibili. |
| Una richiesta ha esito o costo incerto | Non viene considerata gratuita. Controlla il registro richieste e la fatturazione OpenAI prima di autorizzare altri invii. |
| La conferma è disabilitata | Leggi il motivo vicino al controllo: possono mancare foto selezionate, criteri salvati o budget sufficiente per la riserva. |
| La proposta è vuota | Nessuna foto viene inclusa automaticamente: rivedi i criteri oppure includi le foto manualmente. Tutti i file restano disponibili. |
| Lightroom blocca le stelle per XMP | Verifica la preferenza nel catalogo e spunta separatamente l’attestazione nel dialogo del plugin. Il plugin non modifica questa preferenza. |
| Alcune stelle vengono saltate | Controlla la ricevuta. Valutazioni o modifiche manuali intervenute dopo l’importazione non vengono sovrascritte. |

Annulla/ripristina riguarda le decisioni della web app: non ritira richieste API già inviate e non annulla le stelle già applicate in Lightroom.

## Aggiornare e riaprire il progetto

Ferma il backend con **Ctrl+C**. Se hai usato Git, esegui `git pull` dalla cartella del progetto; se hai scaricato lo ZIP, usa una nuova copia del progetto e aggiungi nuovamente il relativo plugin da Gestione plug-in. Poi esegui `scripts/install.command` per aggiornare dipendenze e interfaccia e riavvia `scripts/start.command`.

Dopo modifiche al codice Lua, in **File → Gestione plug-in** seleziona il plugin e usa **Ricarica plug-in / Reload Plug-in**. Se la tua versione non mostra questo comando, rimuovi la registrazione del plugin e aggiungi di nuovo la cartella `.lrplugin`. Ricaricare la pagina web non ricarica il codice del plugin Lightroom.

Servizi, anteprime, cache, piani e ricevute si trovano in **`~/Library/Application Support/LrC Photo Selection/`**, fuori dal repository. L’aggiornamento del codice non richiede di cancellare questa cartella. Non pubblicarla: può contenere fotografie e dati personali. Le chiavi e i token vanno mantenuti privati.

## Verifiche e sviluppo

Il percorso Lightroom → web app → Lightroom è stato provato manualmente su un campione autorizzato, inclusa l’applicazione delle stelle. I controlli automatici usano dati sintetici e simulazioni SDK/API. La nuova distribuzione tra situazioni distinte è coperta da test sintetici; non va confusa con una valutazione estesa della qualità fotografica su servizi reali.

Per preparare l’ambiente di test:

```sh
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest -q
npm --prefix web test -- --run
npm --prefix web run build
```

Su macOS il test Apple Vision richiede il relativo helper compilato. Le prove browser `node scripts/browser_smoke.mjs` e `node scripts/api_browser_smoke.mjs` richiedono Google Chrome e la build web; avviano backend isolati, usano dati sintetici e non aprono Lightroom né chiamano l’API reale.

Approfondimenti: [requisiti](docs/requirements.md), [modelli locali](docs/models.md), [architettura](docs/architecture.md), [analisi OpenAI](docs/openai.md), [guida plugin](docs/plugin-guide.md), [protocollo](shared/README.md) e [risultati delle verifiche](docs/validation.md).

Il provino e il campione OpenAI caricano le righe vicine alla zona visibile, mantenendo l’intera selezione disponibile. Vedi [prestazioni e collaudo con 5.000 foto sintetiche](docs/performance.md).
