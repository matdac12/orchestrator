# Come si legano le entita' — Business Central Zafferano

La domanda vera non e' *quali entita' esistono* (per quella c'e'
`entities.md`), ma *ho un codice articolo, come ricavo tutto quello che si sa
su di lui*. Questo file risponde a quella.

Tutto quanto segue e' stato verificato dal vivo il 2026-08-10 con
`bc_probe.py`. I comandi si possono rieseguire cosi' come sono.

## Le chiavi

- **`Articoli.No` e' il codice articolo**, ed e' la chiave di join universale.
  Esempio reale: `ANG2101`.
- `Dati_Clienti.No` e' il codice cliente (es. `9041950`).
- `Fornitori.No` e' il codice fornitore (es. `19011486`).

## Convenzione dei prefissi sui campi

| Forma | Significato |
|---|---|
| `No`, `Description`, `Unit_Price` | campo Business Central standard |
| `NBT_*` | personalizzazione del partner implementativo |
| `NBT_ZAF_*`, `NBTZAFIT_*` | personalizzazione Zafferano |
| `*_Filter` | **non sono dati**: filtri di pagina, in `$select` non danno nulla di utile |

In `Articoli` la ripartizione e' 45 campi standard, 32 `NBT_*`, 105
`NBT_ZAF_*`, 18 di imballo, 10 filtri.

### Attributi in codice, con il descrittivo accanto

Molti attributi di prodotto sono codici affiancati da un campo `*Desc` con la
descrizione leggibile. Se leggi solo il codice ottieni `1`, che non dice
niente:

```bash
python bc_probe.py query Articoli --filter "No eq 'ANG2101'" \
  --select "NBT_ZAF_Brand,NBT_ZAF_BrandDesc,NBT_ZAF_Family,NBT_ZAF_FamilyDesc"
```
```
NBT_ZAF_Brand  NBT_ZAF_BrandDesc  NBT_ZAF_Family  NBT_ZAF_FamilyDesc
1              AILATI LIGHTS      PF              PRODOTTO FINITO
```

Vale per `Brand`, `Family`, `Style`, `Product_Type`, `Source`, `Source_Type`,
`Main_Material`, `Main_Processing`, `IP`, `Class`, `Dimmable_Product`,
`Battery_Type`, `Thermal_Dissipation`, `Usage` e altri: cerca sempre se
esiste il gemello `*Desc`.

### I numeri non sono numeri

Gli attributi illuminotecnici sono `Edm.String`, non decimali, e usano la
**virgola** come separatore:

```
NBT_ZAF_Total_Watt   Edm.String   ->   "22,2"
```

Quindi: niente `$filter` con confronti numerici (`gt`, `lt`) su questi campi,
e conversione esplicita prima di farci i conti (`float(v.replace(",", "."))`).

## Mappa delle giunzioni

| Da | A | Giunzione | Nota |
|---|---|---|---|
| `Articoli` | `Price_ListLines` | `Articoli.No` = `Price_ListLines.Product_No` | filtra sempre anche per `Price_List_Code`, altrimenti prendi tutti i listini insieme |
| `Articoli` | `DB_Righe` | `Articoli.Production_BOM_No` = `DB_Righe.Production_BOM_No` | **non** `.No` = `.No`: vedi l'avviso sotto |
| `Articoli` | `DBAssemblaggio` | `Articoli.No` = `DBAssemblaggio.Parent_Item_No` | `.No` e' il componente, `.Parent_Item_No` il padre |
| `Articoli` | `Fornitori` | `Articoli.Vendor_No` = `Fornitori.No` | fornitore preferenziale, non lo storico degli acquisti |
| `Articoli` | `RigheAnalisiVenduto` | `Articoli.No` = `RigheAnalisiVenduto.No` | spesso **non serve**: vedi "Quando non fare join" |
| `RigheAnalisiVenduto` | `Dati_Clienti` | `.Sell_to_Customer_No` = `Dati_Clienti.No` | esiste anche `Bill_to_Customer_No`, diverso quando si fattura a un terzo |
| `Price_ListLines` | `Price_List` | `.Price_List_Code` = `Price_List.Code` | la testata porta `Status` e `SourceType` |

### Avviso: la distinta base non si raggiunge dal codice articolo

`DB_Righe.No` **e' il componente**, non il prodotto finito. Il legame al
prodotto passa da `Production_BOM_No`. Invertire i due campi non produce
alcun errore: restituisce zero righe, in silenzio, e sembra che l'articolo non
abbia distinta.

Giusto — 5 componenti:
```bash
python bc_probe.py query DB_Righe --filter "Production_BOM_No eq 'ANG2101'" \
  --select "Line_No,No,Description,Quantity_per"
```
```
10000  MTA04212626006500  MONT. APPLIQUE ANGLED LED ...   1
20000  COV18017329510200  COVER CERAMICA x ANGLED ...     1
30000  IST00029621000000  FOGLIO ISTRUZIONI ...           1
40000  ETC00005003000000  ETICHETTA ... (INTERNA)         1
50000  ETC00008005000000  ETICHETTA ... (ESTERNA)         1
```

Sbagliato — 0 righe, nessun errore:
```bash
python bc_probe.py query DB_Righe --filter "No eq 'ANG2101'" --select "Line_No,No"
```
```
(nessuna riga)
```

Su `ANG2101` il codice distinta coincide con il codice articolo: e' una
convenzione frequente, **non** una regola. Leggi sempre
`Articoli.Production_BOM_No` invece di assumerlo.

Distinta di produzione (`DB_Righe`) e distinta di assemblaggio
(`DBAssemblaggio`) sono due cose diverse: guarda `Articoli.Production_BOM_No`
e `Articoli.Assembly_BOM` per sapere quale delle due esiste per quell'articolo.

## Doppioni da conoscere

`Price_ListLines` e `Listini_prezzi_vendita_righe` espongono **lo stesso
identico insieme di 33 campi**: sono due pagine pubblicate sulla stessa
tabella. Verificato con un diff dei rispettivi `fields`. Usane una sola e resta
coerente.

Piu' in generale, la famiglia `*_Excel` (79 entity set) duplica entita'
operative con un taglio da export. Se non ti serve esattamente quel taglio,
preferisci l'entita' operativa.

## Quando non fare join

`RigheAnalisiVenduto` e' **denormalizzata**: 208 campi che portano gia' dentro
gli attributi di prodotto e i dati di cliente e spedizione. Per l'analisi del
venduto la join ad `Articoli` e a `Dati_Clienti` e' quasi sempre inutile.

Attenzione pero': qui gli stessi attributi hanno il nome **senza** prefisso.

| In `Articoli` | In `RigheAnalisiVenduto` |
|---|---|
| `NBT_ZAF_Total_Watt` | `Total_Watt` |
| `NBT_ZAF_Brand` | `Brand` |
| `NBT_ZAF_Collection` | `Collection` |
| `NBT_ZAF_IP` | `IP` |

Copiare un `$select` da una query all'altra fallisce per questo motivo. Le
descrizioni qui si chiamano `*_Description` (es. `Brand_Description`), non
`*Desc`.

## Ricette

Ognuna e' stata eseguita; i conteggi riportati sono quelli reali.

### 1. Tutto sull'articolo X

```bash
# scheda
python bc_probe.py query Articoli --filter "No eq 'ANG2101'" \
  --select "No,Description,Base_Unit_of_Measure,Vendor_No,Item_Category_Code,Production_BOM_No,Assembly_BOM"
# attributi di prodotto leggibili
python bc_probe.py query Articoli --filter "No eq 'ANG2101'" \
  --select "NBT_ZAF_BrandDesc,NBT_ZAF_FamilyDesc,NBT_ZAF_Total_Watt,NBT_ZAF_IPDesc,NBT_ZAF_Color_Temperature"
# in quali listini compare
python bc_probe.py query Price_ListLines --filter "Product_No eq 'ANG2101'" \
  --select "Price_List_Code,Unit_Price,CurrencyCode,Minimum_Quantity"
```
`ANG2101` compare in 1 listino, a 238.

### 2. Listino completo per codice

```bash
python bc_probe.py query Price_ListLines --filter "Price_List_Code eq '1'" \
  --select "Product_No,Unit_Price,CurrencyCode,Minimum_Quantity"
```
Il listino `1` ("Listino Aziendale") ha **5916 righe**: arrivano tutte solo
perche' il probe segue `@odata.nextLink`. Le testate, con `Status` e
`SourceType`, stanno in `Price_List`:

```bash
python bc_probe.py query Price_List --select "Code,Description,SourceType,Status"
```
`SourceType` vale `All Customers`, `Customer` o `Customer Price Group`, e
determina a chi si applica il listino. `Status` distingue `Active` da `Draft`:
filtrare per `Status eq 'Active'` evita di leggere bozze.

### 3. Distinta esplosa

Due passaggi: prima leggi il codice distinta, poi filtra le righe.

```bash
python bc_probe.py query Articoli --filter "No eq 'ANG2101'" --select "No,Production_BOM_No"
python bc_probe.py query DB_Righe --filter "Production_BOM_No eq 'ANG2101'" \
  --select "Line_No,No,Description,Quantity_per,Unit_of_Measure_Code"
```
5 componenti. Per esplodere piu' livelli, ripeti il primo passaggio su ogni
componente che abbia a sua volta un `Production_BOM_No`.

### 4. Venduto per articolo, senza join

```bash
python bc_probe.py query RigheAnalisiVenduto --filter "No eq 'ANG2101'" \
  --select "Posting_Date,Sell_to_Customer_No,Quantity,Unit_Price,Brand,Collection,Total_Watt,IP"
```
Restituisce gia' cliente, quantita', prezzo e attributi di prodotto insieme.
Per restringere il periodo, `Posting_Date` e' una data vera:
`--filter "No eq 'ANG2101' and Posting_Date gt 2026-01-01"`.
