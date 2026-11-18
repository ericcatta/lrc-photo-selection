# Modelli: verifica preliminare, nessuna prestazione dimostrata

Mac rilevato: M1 Max, 64 GB RAM. Modello attivo: Qwen3.5-9B MLX 4 bit, runtime MLX-VLM 0.4.3, scelto esplicitamente dal proprietario dopo la prova sintetica. Il precedente Qwen3-VL-4B è stato rimosso. La copertura delle categorie non è ancora validata; vedere esiti e decisione finale sotto.

| Candidato | Evidenza primaria | Decisione iniziale |
|---|---|---|
| SigLIP 2 base | https://huggingface.co/google/siglip2-base-patch16-224 — encoder immagine/testo, Apache-2.0 | Primo encoder opzionale, caricamento solo da percorso locale e revisione fissata. Somiglianza non prova equivalenza. |
| DINOv3 ViT-S | https://huggingface.co/facebook/dinov3-vits16-pretrain-lvd1689m — gated, licenza Meta specifica | Rinviato; valutare accesso e termini prima del download. |
| Mapika decider-4b | https://huggingface.co/Mapika/decider-4b e https://github.com/Mapika/decider — variante visiva strutturata; pesi dichiarati Apache-2.0, cautele sui dati di training | Compatibilità Mac visiva non dimostrata; non installare inizialmente. |
| LFM2.5-VL-3B | https://huggingface.co/LiquidAI/LFM2.5-VL-3B-MLX-8bit — export ufficiale Apple Silicon | Licenza LFM Open License v1.0 con condizioni; candidato successivo, non confondere col 24B-A2B testuale. |
| Qwen3-VL-4B | https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct — Apache-2.0; percorso MLX disponibile | Termine di confronto successivo se il benchmark dimostra necessità. |
| Apple Vision | https://developer.apple.com/documentation/vision/detecting-objects-in-still-images | Rilevamento locale di volti/landmark; non riconoscimento identità. |
| InsightFace | https://github.com/deepinsight/insightface/blob/master/python-package/docs/model_zoo.md | Licenze dei pesi non equivalenti al codice; non incorporare modelli non commerciali senza valutazione. |

LAION aesthetic predictors non selezionati: checkpoint/licenza/validità da verificare se emerge un problema misurato. OpenJev, Laya, SemIf-OpenJev e Bespoke-Nimble-9B non adottati: non si presume supporto immagini, disponibilità Mac o licenza commerciale. Queste voci rimangono da verificare prima di qualunque adozione, non sono dipendenze del prodotto.

## Protocollo di benchmark
Campione autorizzato con annotazioni manuali: cambi di persona, pose/risate, raffiche, momenti unici mossi, volti piccoli/di profilo/coperti, due fotocamere. Separare calibrazione e verifica. Registrare ID del campione senza originali in Git, checksum delle anteprime, modello/revisione/runtime/risoluzione, criteri e soglie. Misurare innanzitutto situazioni perse, composizioni unite erroneamente, immagini uniche escluse e blocchi violati. Poi doppioni, tempo, memoria e costo. Non pubblicare soglie arbitrarie come validate.

## Runtime locale aggiunto il 18 novembre 2026

- Qwen3-VL-4B-Instruct, conversione MLX 4 bit: `mlx-community/Qwen3-VL-4B-Instruct-4bit`, revisione `2fd8dacbdb8f1e54b8c005f081ec5bf79c56376b`, licenza dichiarata Apache-2.0. MLX-VLM 0.3.9; dipendenze effettive in requirements-local-ai-lock.txt. Anteprime temporanee max 448 pixel per inferenza, limite che può perdere soggetti piccoli. Nessuna identificazione nominale.
- SigLIP 2 base scaricato alla revisione `75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2`; adattatore di confronto opzionale. Non sostituisce l’esecuzione delle istruzioni libere.
- Download esplicito con scripts/setup_local_model.py; mai durante import/analisi. Caricamento da directory locale, codice remoto disabilitato. Hash dei pesi/config e revisione prompt in cache.

Fonti: https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct ; https://huggingface.co/mlx-community/Qwen3-VL-4B-Instruct-4bit ; https://github.com/Neywa-Labs/mlx-vlm .

La correttezza generale delle istruzioni non è dimostrata da una risposta JSON valida. Servono prove positive, negative, preferenze, conflitti, immagini ambigue e confronto manuale. I risultati dei modelli sono interpretazioni, non fatti importati.


## Ricerca del 18 novembre 2026, dopo il test locale

Hardware nuovamente rilevato: MacBook Pro M1 Max, 10 core CPU, 64 GB di memoria unificata. La scelta tiene conto anche della latenza sulle raccolte, non solo della possibilità di caricare i pesi.

| Candidato | Valutazione per questo progetto |
|---|---|
| Qwen3.5-9B MLX 4 bit | Candidato preferito per il nuovo collaudo: modello visivo/testuale, Apache-2.0, circa 6 GB di pesi. Il produttore riporta risultati generali incoraggianti su comprensione visiva e istruzioni; non sono misure della selezione fotografica o della conversione quantizzata. |
| Qwen3-VL-4B attuale | Più piccolo e già integrato. Il precedente fallimento 150/160 comprendeva problemi di integrazione; non basta a condannare il modello. Rimane il riferimento del confronto tecnico. |
| Qwen3-VL-8B | Alternativa nella stessa famiglia, con licenza Apache-2.0. Non installata: Qwen3.5-9B offre una candidatura più interessante nella stessa fascia di memoria, da verificare sul nostro flusso. |
| Qwen3-VL-32B | Può essere plausibile quantizzato con 64 GB, ma maggiore memoria e latenza non sono giustificate da misure di beneficio nel nostro caso. Non installato. |
| Liquid LFM2.5-VL-3B | Interessante per velocità/dispositivi limitati, ma licenza specifica LFM e nessun vantaggio dimostrato nel culling in italiano. Non installato. |
| Mapika decider-4b v3 | Supporta immagini, ma restituisce decisioni tipizzate su opzioni esplicite anziché essere un sostituto diretto del nostro interprete generativo. Richiederebbe un diverso adattatore; nessun vantaggio misurato che lo giustifichi ora. |

Fonti primarie consultate:
- [Qwen3.5-9B, scheda e benchmark del produttore](https://huggingface.co/Qwen/Qwen3.5-9B)
- [Licenza originale Apache 2.0](https://huggingface.co/Qwen/Qwen3.5-9B/blob/main/LICENSE)
- [Conversione MLX 4 bit](https://huggingface.co/mlx-community/Qwen3.5-9B-MLX-4bit)
- [Qwen3-VL-8B](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct)
- [LFM2.5-VL-3B](https://huggingface.co/LiquidAI/LFM2.5-VL-3B)
- [Decider v3](https://huggingface.co/Mapika/decider-4b)
- [Runtime MLX-VLM](https://github.com/Neywa-Labs/mlx-vlm)

La preferenza per 9B è una decisione ingegneristica, non la dimostrazione che sia universalmente il migliore. Non esiste in queste fonti un benchmark corrispondente a preferenze personali, varietà di un servizio e merito fotografico. La selezione dell'intera raccolta resta responsabilità della pipeline; cambiare modello non sostituisce le regole di copertura.

Il controllo riproducibile `scripts/check_local_model.py` usa soltanto forme geometriche generate e istruzioni italiane. Misura caricamento, memoria MLX e risposte strutturate; non accede ai servizi o alle foto dell'utente e non valuta l'estetica. Usa lo stesso adattatore dell'app, offline e con thinking disabilitato. I risultati reali su Campione di prova restano da verificare manualmente.

### Esito della prova e decisione

**Nessuna sostituzione attivata.** Rimane Qwen3-VL-4B con runtime 0.3.9 e prompt v6 già corretto. Questo non significa che sia stato dimostrato il modello migliore: il candidato 9B non ha superato il requisito funzionale minimo del confronto.

| Configurazione | Controlli attesi superati | Tempo totale | Picco memoria MLX |
|---|---:|---:|---:|
| Qwen3-VL-4B, runtime 0.3.9 | 2/5 | 35,0 s | 4,27 GB |
| Qwen3.5-9B, runtime 0.4.3 isolato | 3/5 | 93,4 s | 7,70 GB |

Il 9B riconosce cerchio rosso e quadrato blu ma esclude ciascuna immagine perché manca l'altra categoria: non rispetta la copertura tra immagini prevista dall'app. Il 4B in questa prova non ricava le categorie geometriche e sbaglia i due casi positivi. Entrambi generano risposte strutturalmente valide: la validazione JSON da sola non prova comprensione corretta. Le differenze includono anche il runtime, quindi non sono attribuibili esclusivamente ai pesi. Picco MLX non equivale alla memoria totale del Mac. Tempi non estrapolabili a un matrimonio.

Report sintetici completi: [4B](benchmarks/local-model-4b.json), [9B](benchmarks/local-model-9b.json). Per ripetere il candidato occorre MLX-VLM 0.4.3; è stato valutato da un pacchetto estratto temporaneamente, senza aggiornare la .venv attiva. Revisione pesi 9B: `938d8919941c6e7efd3c7150eff7fe9d12afa631`. Il suo download viene rimosso dopo la prova negativa, evitando un secondo modello inutilizzato. Nessuna foto reale, decisione, stella o richiesta API coinvolta.

Prima di cambiare modello, il criterio di accettazione resta: categorie distinte conservate nell'insieme, nessun obbligo inventato di compresenza nella singola foto, casi positivi e negativi corretti, quindi confronto umano sul campione reale. Non dichiarare risolto questo comportamento sulla base dei soli test unitari.


### Decisione successiva del proprietario: attivare comunque Qwen3.5-9B

Dopo aver letto l'esito negativo del controllo di copertura, il proprietario ha chiesto esplicitamente di sostituire il 4B con il 9B e rimuovere il precedente. La decisione iniziale di non sostituire, sopra riportata, è quindi superata. Si adotta Qwen3.5-9B MLX 4 bit, revisione `938d8919941c6e7efd3c7150eff7fe9d12afa631`, con MLX-VLM 0.4.3. Il limite sulla copertura delle categorie resta aperto: non è dichiarato risolto o validato. Nessuna nuova analisi delle fotografie viene avviata dall'installazione.

Il modello attivo è selezionato esplicitamente in `local-model-selection.json` nello spazio dati locale. Lo script di installazione permette `--model Qwen3.5-9B-MLX-4bit --activate`; il caricamento durante l'analisi resta offline. Il precedente 4B viene eliminato solo dopo verifica dei file e della selezione attiva. SigLIP 2 è un encoder distinto e rimane, perché non è il modello sostituito.
