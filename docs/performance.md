# Prestazioni del provino con 5.000 foto

Il provino mantiene nel browser soltanto le righe visibili e alcune righe vicine.
L’elenco completo resta disponibile per filtri, conteggi, decisioni manuali,
confronto e anteprima navigabile. Le righe sono misurate per mantenere la griglia
responsiva e le motivazioni espandibili; il focus da tastiera può raggiungere
anche una foto non ancora visualizzata. Non ci sono pagine o un pulsante “carica altre”.

Anche il campione OpenAI usa una lista virtualizzata. La selezione delle caselle
resta separata dalle righe montate; l’elenco esatto della stima viene creato solo
quando aperto. Nessuna analisi parte per effetto dello scorrimento o dei filtri.
La cache HTTP e le protezioni di autenticazione restano invariate.

## Verifica riproducibile

Dopo aver installato le dipendenze di sviluppo e compilato il frontend:

```sh
PYTHONPATH=backend node scripts/scale_browser_smoke.mjs
```

Richiede Google Chrome nel percorso macOS standard. Il test avvia un backend
isolato sulla porta 18767, con 5.000 record sintetici e una sola immagine di forme
generate, collegata ai diversi record. Non accede a foto reali, cataloghi o
credenziali. Non effettua analisi cloud. `LRC_SMOKE_WEB_DIR` consente di verificare
una build separata senza sostituire quella installata.

Nel confronto iniziale sullo stesso Mac e con Chrome headless a 1500 × 1100:

| Misura | Prima | Dopo |
| --- | ---: | ---: |
| Schede montate inizialmente | 5.000 | 20 |
| Elementi DOM | 140.133 | 727 |
| Prima visualizzazione | 1.135 ms | 223 ms |
| Esclusione con conferma di copertura | 1.672 ms | 219 ms |

Sono misure sintetiche indicative, non una garanzia dei tempi su altri Mac o
su Safari. Il test controlla anche annulla/ripristina, filtri, fondo del provino,
ridimensionamento, navigazione da tastiera tra righe non montate, anteprima,
mobile a 390 px e conservazione delle decisioni. Il campione OpenAI verifica
selezione e deselezione senza invio. Nessuna modifica al backend di produzione,
al plugin Lua, ai cataloghi, alle foto originali o ai sidecar è necessaria.
