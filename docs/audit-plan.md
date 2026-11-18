# Audit e implementazione — novembre 2026

## Ordine di consegna approvato

1. Piani stelle immutabili confermati, ripresa del piano attivo, annullamento dentro il write gate, ricevute persistenti; criteri non supportati dichiarati e revisione coerente.
2. Collaudo reale sul catalogo JPEG autorizzato, mai sul 2026. L'assenza di controllo grafico non autorizza ad aprire Lightroom genericamente o a leggere il database del catalogo.
3. Servizi incrementali nello stesso catalogo, archivio locale, decisioni annullabili, confronto e scorciatoie.
4. Evidenze locali e ritagli dei volti; calibrazione su un campione reale autorizzato prima di usare somiglianza per ridurre candidate.
5. Raccolta Classic facoltativa locale, soltanto dopo collaudo SDK e verifica della mancata sincronizzazione. Disattivata per impostazione predefinita; nessuna scrittura di raccolte nella versione corrente.

Le fasi implementabili con dati sintetici possono procedere mentre il collaudo grafico è bloccato. Questo non equivale ad aver superato la verifica Lightroom.

## Riferimenti di prodotto

- Narrative: dettagli dei volti accanto alla foto intera, mantenendo il contesto. https://help.narrative.so/en/articles/7337371-zoom-and-close-ups-in-narrative
- Aftershoot: revisione assistita di gruppi e duplicati con scelta manuale. https://support.aftershoot.com/en/articles/5223473-get-started-with-aftershoot-culling
- Adobe Assisted Culling: criteri e risultati consultabili. https://helpx.adobe.com/lightroom-classic/desktop/organize-photos-in-lightroom-classic/assisted-culling.html
- Una raccolta Classic non richiede sincronizzazione: l'opzione Sync with Lightroom è distinta. Questo dato di prodotto non prova da solo il comportamento dell'SDK. https://helpx.adobe.com/uk/lightroom-classic/desktop/organize-photos-in-lightroom-classic/photo-collections.html

Non vengono copiati sviluppo, cancellazioni, flags o automatismi di esclusione basati unicamente sulla qualità.

## Evidenze locali

Le estrazioni leggono solo anteprime già importate. La cache `feature-cache.sqlite3` nella directory dati dell'app contiene risultati riusciti indicizzati da SHA-256 dell'anteprima e identità del componente. Per SigLIP l'identità include i pesi/configurazioni e il runtime; per Apple Vision include hash dell'eseguibile e versione del sistema. Un'interruzione mantiene la cache già scritta; errori di rilevamento non sono memorizzati come risultati validi. Il risultato complessivo viene applicato solo alla revisione di servizio verificata.

I vicini nello spazio visivo sono suggerimenti di confronto, non gruppi di equivalenza o esclusioni. Nessuna soglia è dichiarata calibrata. I ritagli di volti provengono da coordinate Apple Vision normalizzate con origine in basso a sinistra; non rappresentano identità, presenza certa di tutte le persone o valutazioni affidabili degli occhi.

## Benchmark sintetico riproducibile

Eseguire `.venv/bin/python scripts/benchmark_scale.py`. Crea due directory temporanee isolate, importa 1.000 e 5.000 metadati sintetici, una singola anteprima uniforme per ciascun servizio, misura lettura dettaglio e richieste anteprima e avvia il motore conservativo. Le altre immagini prive di anteprima devono restare candidate. Non misura importazione di migliaia di JPEG, rendering browser di migliaia di miniature, accuratezza IA o prestazioni su RAW.

Il benchmark umano resta `scripts/benchmark.py`: annotare situazioni significative, immagini uniche e coppie da non raggruppare; confrontare separatamente calibrazione e verifica. Nessuna fotografia personale o annotazione identificativa va nel repository.
