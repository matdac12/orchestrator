# zafferano-bc — design

Data: 2026-08-10
Stato: approvato in brainstorming, da implementare

## Problema

La conoscenza di come Zafferano usa Microsoft Dynamics 365 Business Central e'
sparsa su almeno otto progetti, in due alberi diversi
(`Documents\Zafferano` e `OneDrive - Be Digital Consulting Srl\Zafferano`).
Ogni volta che un agente entra in uno di quei progetti rifa' la stessa
indagine da zero: trova l'auth leggendo un `bc_connection.py`, scopre i nomi
delle entita' leggendo le query, e reinciampa nelle stesse trappole.

Il costo non e' solo di token. Alcune trappole sono silenziose: chi non sa che
la paginazione va seguita legge la prima pagina e crede di aver letto tutto.

## Obiettivo

Una skill invocabile — `zafferano-bc` — che dia a un agente, senza indagine,
tutto quello che serve per leggere Business Central di Zafferano: auth,
URL, entita', struttura dei dati (listini, prodotti, anagrafiche), trappole.
Piu' la possibilita' di interrogare BC dal vivo quando la documentazione non
basta.

## Non-obiettivi

- **Nessuna mappa progetto-per-progetto.** La skill descrive Business
  Central, non i progetti che lo consumano. Un agente dentro `Klaviyo` deve
  poter chiedere "come leggo le anagrafiche clienti" e ricevere l'entita'
  giusta, non la cronaca di cosa fa il progetto Klaviyo. Questo tiene la
  skill condivisibile fra progetti e team, e non la fa marcire quando nasce
  il nono progetto.
- **Nessuna scrittura su BC.** L'uso reale rilevato e' in sola lettura.
  La skill documenta la lettura; se un giorno servira' scrivere, e' un
  intervento separato.
- **Nessun segreto nei file della skill.** Vedi "Credenziali".

## Contesto rilevato (verificato dal vivo il 2026-08-10)

- Auth: OAuth2 client credentials via Azure AD, scope
  `https://api.businesscentral.dynamics.com/.default`. Token valido 1 ora.
- Tenant `75504027-0c82-4005-973f-d2196c2680ff`, environment `IT-Prod`,
  company `Zafferano S.r.l.`. Gia' presenti in CLAUDE.md versionati: non
  sono segreti.
- Il tenant pubblica **231 entity set**. I progetti ne usano circa 25.
- Le entita' sono in larga parte pagine AL custom con nomi italiani
  (`Articoli`, `Fornitori`, `Dati_Clienti`, `DB_Righe`, `DBAssemblaggio`,
  `RigheAnalisiVenduto`, `Listini_prezzi_vendita_righe`, ...): non
  deducibili, non presenti nella documentazione standard Microsoft.
- Convenzione env gia' in uso ovunque: `BC_TENANT_ID`, `BC_CLIENT_ID`,
  `BC_CLIENT_SECRET`, `BC_ENVIRONMENT`, `BC_COMPANY`.

## Architettura

Skill in `.claude/skills/zafferano-bc/` nel repo orchestrator (hub
user-level, junction verso `~/.claude`), stessa forma di `clockify-report`
(SKILL.md + helper Python).

```
zafferano-bc/
├── SKILL.md
├── references/
│   └── entities.md
└── bc_probe.py
```

Il principio che regge la struttura e' la **divulgazione progressiva**: 231
entita' con i loro campi non stanno in un file leggibile. SKILL.md risponde
al caso comune senza aprire altro; `entities.md` copre il resto; il probe
copre quello che nessun file puo' anticipare.

### SKILL.md — sempre caricato

Target ~150 righe. Contiene:

1. **Auth**, in forma compatta: token endpoint, scope, durata, variabili env.
2. **I due URL, e perche' contano.**
   - radice: `.../v2.0/{tenant}/{env}/ODataV4/` — qui stanno il service
     document (elenco entity set) e `$metadata` (campi).
   - dati: `{radice}Company('Zafferano S.r.l.')/`
   Interrogare il service document sotto `Company('...')` risponde con una
   lista vuota e fa credere che il tenant non pubblichi niente. E' gia'
   costato tempo a qualcuno: va per primo.
3. **Trappole**: paginazione `@odata.nextLink` (ignorarla legge solo la prima
   pagina, in silenzio); nomi italiani non deducibili; qualche nome con
   encoding rotto (`Scheda_unit�_di_stockkeeping_Excel`) — leggere UTF-8;
   token da rinnovare oltre l'ora; in pratica sola lettura.
4. **Orientamento sulle entita' principali** — non un catalogo, una mappa:
   articoli, listini vendita e acquisto, anagrafiche clienti/fornitori/agenti,
   distinte basi, ordini, movimenti, famiglia Power BI. Per ciascuna, una
   riga su cosa contiene davvero e come si lega alle altre.
5. **Come usare il probe**, con esempi.
6. **Quando aprire `references/entities.md`.**

### references/entities.md

- Tutti i 231 entity set, raggruppati per dominio (anagrafiche, listini,
  articoli e distinte, vendite, acquisti, movimenti contabili, export Excel,
  Power BI, workflow/OData standard). Solo nomi: costa poco e rende
  scopribile ogni entita'.
- Catalogo campi completo per le entita' core (quelle in uso reale, ~25),
  estratto dal `$metadata` dal vivo.
- Struttura dei dati di dominio: com'e' fatto un listino (testata/righe,
  codice listino, come si filtra), come articoli e distinte basi si legano,
  cosa distingue le anagrafiche.

### bc_probe.py

```
python bc_probe.py list [--grep PATTERN]        # entity set pubblicati
python bc_probe.py fields <Entity>              # campi reali da $metadata
python bc_probe.py query <Entity> [--filter F] [--select S] [--top N]
python bc_probe.py raw "<path OData>"           # via di fuga
```

`query` segue `@odata.nextLink` di default, con `--top` per fermarsi prima.

Output tabellare allineato di default — un agente che ispeziona dati legge
meglio una tabella che un muro di JSON — e `--json` quando serve il dato
grezzo da reinstradare. `fields` stampa sempre tabellare (nome, tipo,
nullable). `raw` stampa sempre JSON: e' la via di fuga, non deve
interpretare.

## Credenziali

Risoluzione in ordine, si ferma alla prima che funziona:

1. `BC_*` gia' presenti nell'ambiente;
2. `.env` nella directory di lavoro corrente o nella radice del progetto;
3. elenco documentato di percorsi `.env` noti sulla macchina di Mattia.

Il passo 3 e' il motivo per cui la skill funziona da qualunque progetto senza
setup. E' anche il passo specifico di questa macchina: va isolato in una
costante in cima a `bc_probe.py`, dichiarato come tale, cosi' chi riceve la
skill condivisa sa cosa cambiare.

Nei file della skill non entrano `BC_CLIENT_SECRET` ne' altri segreti. Il
probe non stampa mai il valore di un segreto, nemmeno in errore: un fallimento
di auth riporta quale variabile mancava e da quale fonte, non il contenuto.

Tenant, environment e company restano in chiaro: sono gia' in CLAUDE.md
versionati e senza il secret non aprono niente.

## Costruzione

Il catalogo si estrae dal vivo (`$metadata`), non si deduce dal codice: e'
l'unica fonte che elenca anche le entita' che nessun progetto ha ancora
toccato, e i campi completi invece di quelli citati per caso.

La conoscenza di dominio — cosa significa un'entita', come si lega alle
altre, quali filtri hanno senso — si ricava leggendo il codice dei progetti
esistenti, che e' dove quella semantica e' stata capita la prima volta.
Entra nella skill in forma generale, mai come "il progetto X fa Y".

## Verifica

La skill si considera finita quando:

1. ogni sottocomando del probe e' stato eseguito davvero e il suo output e'
   riportato — non "dovrebbe funzionare";
2. il probe funziona lanciato da una directory che non e' un progetto
   Zafferano (dimostra che la risoluzione credenziali regge);
3. le affermazioni sui campi in `entities.md` sono confrontate con il
   `$metadata` dal vivo, non con il mio riassunto di poco prima;
4. un fallimento di auth simulato (secret errato) produce un errore
   comprensibile e non stampa il secret;
5. il conteggio degli entity set in `entities.md` corrisponde a quanto
   risponde il service document.

## Rischi

- **Il catalogo invecchia.** Se Zafferano pubblica nuove pagine AL,
  `entities.md` resta indietro. Mitigazione: il probe e' la fonte di
  verita' e SKILL.md dice esplicitamente di usarlo quando l'entita' cercata
  non e' in elenco.
- **231 entita' tentano l'esaustivita'.** Documentare i campi di tutte
  produrrebbe un file inutilizzabile. Il campo dettagliato resta limitato
  alle core; per le altre bastano nome e dominio piu' il probe.
