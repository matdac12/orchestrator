---
name: zafferano-bc
description: Come si legge il Business Central di Zafferano — auth, endpoint, entita' pubblicate, come si legano fra loro a partire dal codice articolo, e un probe per interrogarlo dal vivo. Listini, articoli, anagrafiche, distinte basi, venduto.
user-invocable: true
disable-model-invocation: true
---

# Business Central di Zafferano

Tutto quello che serve per leggere il BC di Zafferano senza rifare l'indagine
ogni volta. Verificato dal vivo su `IT-Prod` il 2026-08-10.

> Questa skill si attiva **solo** quando la invochi tu con `/zafferano-bc`.
> Nessun agente la carica da solo.

## I due URL — la cosa che costa piu' tempo a chi non la sa

```
radice   https://api.businesscentral.dynamics.com/v2.0/{tenant}/{env}/ODataV4/
dati     {radice}Company('Zafferano S.r.l.')/
```

Il **service document** (elenco delle entita') e **`$metadata`** (campi) stanno
alla **radice**. I dati stanno sotto `Company('...')`.

Interrogare il service document sotto `Company('...')` risponde con una lista
vuota: sembra che il tenant non pubblichi niente, e invece pubblica 231 entity
set. Se ti capita, e' questo.

## Auth

OAuth2 client credentials via Azure AD.

```
POST https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token
     grant_type=client_credentials
     scope=https://api.businesscentral.dynamics.com/.default
```

Token valido **1 ora**. Variabili: `BC_TENANT_ID`, `BC_CLIENT_ID`,
`BC_CLIENT_SECRET`, `BC_ENVIRONMENT`, `BC_COMPANY`.

Tenant `75504027-0c82-4005-973f-d2196c2680ff` · environment `IT-Prod` ·
company `Zafferano S.r.l.`

`bc_probe.py` risolve le credenziali da solo: prima le `BC_*` d'ambiente, poi
un `.env` risalendo dalla directory corrente, poi un elenco di `.env` noti. Non
serve configurare niente per usarlo.

## Trappole, in ordine di quanto costano

1. **Paginazione.** Le risposte sono paginate con `@odata.nextLink`. Chi non
   segue il link legge la prima pagina e non se ne accorge: nessun errore,
   solo dati mancanti. Il listino `1` ha 5916 righe, non una pagina.
2. **La distinta base non si raggiunge dal codice articolo.** Si passa da
   `Articoli.Production_BOM_No` → `DB_Righe.Production_BOM_No`. `DB_Righe.No`
   e' il *componente*. Invertirli restituisce zero righe in silenzio.
3. **Lo stesso attributo cambia nome fra entita'**: `NBT_ZAF_Total_Watt` in
   `Articoli`, `Total_Watt` in `RigheAnalisiVenduto`. Copiare un `$select` da
   una query all'altra fallisce.
4. **Gli attributi tecnici sono stringhe con la virgola**: `Total_Watt` vale
   `"22,2"`, non `22.2`. Niente confronti numerici nel `$filter`.
5. **Gli attributi in codice hanno un gemello `*Desc`**: `NBT_ZAF_Brand` vale
   `1`, `NBT_ZAF_BrandDesc` vale `AILATI LIGHTS`.
6. **I campi `*_Filter` non sono dati**, sono filtri di pagina.
7. **Nomi italiani e non deducibili** (`Articoli`, `DB_Righe`,
   `RigheAnalisiVenduto`), con accenti: leggi e scrivi UTF-8.
8. In pratica **sola lettura**: nessun progetto scrive su BC.

## Le entita' che servono quasi sempre

| Entita' | Cosa contiene |
|---|---|
| `Articoli` | anagrafica articoli, 210 campi. `No` e' il codice articolo, chiave di join universale |
| `Dati_Clienti` | anagrafica clienti, 266 campi |
| `Fornitori` | anagrafica fornitori |
| `Agenti` | agenti di vendita |
| `Price_List` | testate listini: `Code`, `Status` (`Active`/`Draft`), `SourceType` |
| `Price_ListLines` | righe listino: `Product_No`, `Unit_Price`, filtra per `Price_List_Code` |
| `DB_Righe` | righe distinta base di **produzione** |
| `DBAssemblaggio` | righe distinta di **assemblaggio** (`Parent_Item_No`) |
| `RigheAnalisiVenduto` | venduto denormalizzato, 208 campi: cliente + prodotto gia' dentro |
| `ItemLedgerEntries` | movimenti di magazzino |
| `Ordini_di_Vendita` + `Ordini_di_VenditaSalesLines` | ordini di vendita, testate e righe |
| `UM`, `Ubicazioni`, `Collocazioni` | tabelle di servizio |

Sono 231 in tutto: le altre stanno in `references/entities.md`.

## Il probe

```bash
python bc_probe.py list [--grep listin]              # entity set pubblicati
python bc_probe.py fields Articoli [--grep lumen]    # campi reali da $metadata
python bc_probe.py query Articoli --filter "No eq 'ANG2101'" --select "No,Description" [--top 5] [--json]
python bc_probe.py raw "Company('Zafferano S.r.l.')/UM?\$top=2"
```

`query` segue la paginazione da solo. Su un `$select` sbagliato, BC dice quale
proprieta' non esiste e il probe te lo riporta invece di uno stack trace.

## Dove guardare dopo

- **`references/relazioni.md`** — come le entita' si legano: mappa delle
  giunzioni, convenzioni sui nomi dei campi, quando *non* fare join, e quattro
  ricette pronte (tutto su un articolo, listino completo, distinta esplosa,
  venduto per articolo). **E' il file da aprire per primo** se devi partire da
  un codice articolo.
- **`references/entities.md`** — le 231 entita' raggruppate per dominio e i
  campi delle 22 principali.
- **il probe** quando l'entita' che cerchi non e' in elenco: i due file sono una
  fotografia del 2026-08-10, `$metadata` e' la verita' corrente.
