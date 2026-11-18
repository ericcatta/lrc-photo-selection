# Modelli: verifica preliminare, nessuna prestazione dimostrata

Mac rilevato: M1 Max, 64 GB RAM. Nessun modello è stato provato sulle foto dell'utente.

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
