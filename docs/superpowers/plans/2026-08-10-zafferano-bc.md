# zafferano-bc Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Una skill `zafferano-bc` che dia a qualunque agente, senza indagine, la conoscenza di Business Central di Zafferano — auth, entita', come le entita' si legano fra loro a partire dal codice articolo — piu' un probe per interrogare BC dal vivo.

**Architecture:** Skill in `.claude/skills/zafferano-bc/` con divulgazione progressiva: `SKILL.md` risponde al caso comune, `references/relazioni.md` porta la mappa delle giunzioni (il cuore), `references/entities.md` il catalogo delle 231 entita', `bc_probe.py` copre cio' che nessun file puo' anticipare. La logica pura del probe (risoluzione credenziali, parsing `$metadata`, costruzione URL, paginazione, resa tabellare) e' separata dall'I/O di rete, cosi' e' testabile offline.

**Tech Stack:** Python 3.11, `requests`, `python-dotenv`, `xml.etree.ElementTree` (stdlib), pytest. Nessuna dipendenza nuova: tutte gia' presenti.

## Global Constraints

- Nessun segreto nei file della skill. `BC_CLIENT_SECRET` non compare mai in codice, documentazione, output o messaggi di errore.
- Tenant `75504027-0c82-4005-973f-d2196c2680ff`, environment `IT-Prod`, company `Zafferano S.r.l.` restano in chiaro: gia' in CLAUDE.md versionati.
- Variabili env, nomi esatti: `BC_TENANT_ID`, `BC_CLIENT_ID`, `BC_CLIENT_SECRET`, `BC_ENVIRONMENT`, `BC_COMPANY`.
- Il service document e `$metadata` stanno alla radice `/ODataV4/`, i dati sotto `Company('Zafferano S.r.l.')/`. Mai invertirli.
- Scope OAuth: `https://api.businesscentral.dynamics.com/.default`. Token valido 1 ora.
- La skill descrive Business Central, mai i progetti che lo consumano. Nessuna frase del tipo "il progetto X usa Y".
- Test in `tests/`, convenzione del repo. Si lanciano con `python -m pytest tests/ -v` dalla radice del repo.
- Tutti i file di testo in UTF-8. Alcuni nomi di entita' contengono accenti (`Scheda_unità_di_stockkeeping_Excel`): leggere e scrivere esplicitamente in UTF-8, mai affidarsi al default di Windows.
- I percorsi `.env` specifici di questa macchina stanno in **una sola costante** in cima a `bc_probe.py`, marcata come tale.

---

### Task 1: Risoluzione credenziali e autenticazione

**Files:**
- Create: `.claude/skills/zafferano-bc/bc_probe.py`
- Test: `tests/test_bc_probe.py`

**Interfaces:**
- Consumes: niente (primo task)
- Produces:
  - `REQUIRED_KEYS: tuple[str, ...]` = `("BC_TENANT_ID", "BC_CLIENT_ID", "BC_CLIENT_SECRET")`
  - `KNOWN_ENV_PATHS: list[str]` — costante machine-specific
  - `choose_env_file(start_dir: Path, candidates: list[Path], exists) -> Path | None`
  - `resolve_credentials(environ: dict, env_values: dict) -> tuple[dict, list[str]]` — ritorna `(creds, missing_keys)`
  - `CredentialError(Exception)` con attributo `.missing: list[str]` e `.source: str`
  - `load_credentials(start_dir: Path | None = None) -> tuple[dict, str]` — ritorna `(creds, source_description)`
  - `get_token(creds: dict) -> str`
  - `root_url(creds: dict) -> str`, `company_url(creds: dict) -> str`

- [ ] **Step 1: Write the failing test**

Crea `tests/test_bc_probe.py`:

```python
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "zafferano-bc"
sys.path.insert(0, str(SKILL_DIR))

import bc_probe  # noqa: E402


def test_choose_env_file_prefers_nearest_walking_up():
    present = {Path("/proj/sub/.env"), Path("/known/.env")}
    got = bc_probe.choose_env_file(
        Path("/proj/sub/deep"),
        [Path("/known/.env")],
        exists=lambda p: p in present,
    )
    assert got == Path("/proj/sub/.env")


def test_choose_env_file_falls_back_to_known_paths():
    present = {Path("/known/.env")}
    got = bc_probe.choose_env_file(
        Path("/elsewhere"),
        [Path("/known/.env")],
        exists=lambda p: p in present,
    )
    assert got == Path("/known/.env")


def test_choose_env_file_returns_none_when_nothing_exists():
    got = bc_probe.choose_env_file(
        Path("/elsewhere"), [Path("/known/.env")], exists=lambda p: False
    )
    assert got is None


def test_environ_wins_over_env_file():
    creds, missing = bc_probe.resolve_credentials(
        environ={"BC_TENANT_ID": "from-env", "BC_CLIENT_ID": "c", "BC_CLIENT_SECRET": "s"},
        env_values={"BC_TENANT_ID": "from-file"},
    )
    assert creds["BC_TENANT_ID"] == "from-env"
    assert missing == []


def test_defaults_applied_for_environment_and_company():
    creds, _ = bc_probe.resolve_credentials(
        environ={"BC_TENANT_ID": "t", "BC_CLIENT_ID": "c", "BC_CLIENT_SECRET": "s"},
        env_values={},
    )
    assert creds["BC_ENVIRONMENT"] == "IT-Prod"
    assert creds["BC_COMPANY"] == "Zafferano S.r.l."


def test_missing_keys_are_reported():
    _, missing = bc_probe.resolve_credentials(
        environ={"BC_TENANT_ID": "t"}, env_values={}
    )
    assert sorted(missing) == ["BC_CLIENT_ID", "BC_CLIENT_SECRET"]


def test_credential_error_message_never_leaks_the_secret():
    err = bc_probe.CredentialError(missing=["BC_CLIENT_ID"], source="/some/.env")
    rendered = str(err)
    assert "BC_CLIENT_ID" in rendered
    assert "/some/.env" in rendered


def test_urls_are_built_root_and_company():
    creds = {
        "BC_TENANT_ID": "TEN",
        "BC_ENVIRONMENT": "IT-Prod",
        "BC_COMPANY": "Zafferano S.r.l.",
    }
    assert bc_probe.root_url(creds) == (
        "https://api.businesscentral.dynamics.com/v2.0/TEN/IT-Prod/ODataV4/"
    )
    assert bc_probe.company_url(creds).endswith("ODataV4/Company('Zafferano S.r.l.')/")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_bc_probe.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bc_probe'`

- [ ] **Step 3: Write minimal implementation**

Crea `.claude/skills/zafferano-bc/bc_probe.py`:

```python
#!/usr/bin/env python3
"""
Probe OData V4 per il Business Central di Zafferano.

Sottocomandi: list, fields, query, raw.  Vedi SKILL.md.

Le credenziali si risolvono in ordine: variabili d'ambiente BC_*, poi un .env
risalendo dalla directory corrente, poi i percorsi noti in KNOWN_ENV_PATHS.
Il segreto non viene mai stampato, nemmeno in caso di errore.
"""

import os
from pathlib import Path

import requests
from dotenv import dotenv_values

# --- SPECIFICO DI QUESTA MACCHINA -------------------------------------------
# Ultimo anello della risoluzione credenziali: percorsi .env noti sulla
# postazione di Mattia. Chi riceve questa skill altrove cambia SOLO questa
# lista (o esporta le BC_* nell'ambiente e la lista non viene nemmeno letta).
KNOWN_ENV_PATHS = [
    r"C:\Users\MattiaDaCampo\Documents\Zafferano\zafferano-portale-listino\sync\.env",
    r"C:\Users\MattiaDaCampo\Documents\Zafferano\ProgettoDistinteBasi\.env",
    r"C:\Users\MattiaDaCampo\Documents\Zafferano\ProgettoKPI\.env",
    r"C:\Users\MattiaDaCampo\OneDrive - Be Digital Consulting Srl\Zafferano\zafferano-ftp-server\.env",
    r"C:\Users\MattiaDaCampo\OneDrive - Be Digital Consulting Srl\Zafferano\Progetto_InvioDocumentiEmail\.env",
]
# ---------------------------------------------------------------------------

REQUIRED_KEYS = ("BC_TENANT_ID", "BC_CLIENT_ID", "BC_CLIENT_SECRET")
DEFAULTS = {"BC_ENVIRONMENT": "IT-Prod", "BC_COMPANY": "Zafferano S.r.l."}

TIMEOUT = 120
WALK_UP_LEVELS = 3


class CredentialError(Exception):
    def __init__(self, missing, source):
        self.missing = missing
        self.source = source
        super().__init__(
            f"Credenziali BC incomplete: mancano {', '.join(missing)}.\n"
            f"Fonte consultata: {source}\n"
            f"Esporta le variabili BC_* oppure aggiungi un .env valido."
        )


def choose_env_file(start_dir, candidates, exists=None):
    """Primo .env risalendo da start_dir (max WALK_UP_LEVELS), poi i candidati."""
    if exists is None:
        exists = lambda p: p.exists()  # noqa: E731

    current = Path(start_dir)
    for _ in range(WALK_UP_LEVELS + 1):
        candidate = current / ".env"
        if exists(candidate):
            return candidate
        if current.parent == current:
            break
        current = current.parent

    for candidate in candidates:
        candidate = Path(candidate)
        if exists(candidate):
            return candidate
    return None


def resolve_credentials(environ, env_values):
    """environ vince su env_values, chiave per chiave. Ritorna (creds, missing)."""
    creds = {}
    for key in REQUIRED_KEYS + tuple(DEFAULTS):
        value = environ.get(key) or env_values.get(key) or DEFAULTS.get(key)
        if value:
            creds[key] = value
    missing = [k for k in REQUIRED_KEYS if not creds.get(k)]
    return creds, missing


def load_credentials(start_dir=None):
    start_dir = Path(start_dir or Path.cwd())
    env_file = choose_env_file(start_dir, KNOWN_ENV_PATHS)
    env_values = dotenv_values(env_file, encoding="utf-8") if env_file else {}
    source = str(env_file) if env_file else "solo variabili d'ambiente"
    creds, missing = resolve_credentials(os.environ, env_values)
    if missing:
        raise CredentialError(missing=missing, source=source)
    return creds, source


def get_token(creds):
    url = f"https://login.microsoftonline.com/{creds['BC_TENANT_ID']}/oauth2/v2.0/token"
    resp = requests.post(
        url,
        data={
            "grant_type": "client_credentials",
            "client_id": creds["BC_CLIENT_ID"],
            "client_secret": creds["BC_CLIENT_SECRET"],
            "scope": "https://api.businesscentral.dynamics.com/.default",
        },
        timeout=TIMEOUT,
    )
    if not resp.ok:
        # Il corpo della risposta Azure non contiene il secret, ma non lo
        # inoltriamo comunque: riportiamo solo codice ed error code.
        code = ""
        try:
            code = resp.json().get("error", "")
        except ValueError:
            pass
        raise RuntimeError(f"Auth fallita (HTTP {resp.status_code}, error={code!r}).")
    return resp.json()["access_token"]


def root_url(creds):
    return (
        "https://api.businesscentral.dynamics.com/v2.0/"
        f"{creds['BC_TENANT_ID']}/{creds['BC_ENVIRONMENT']}/ODataV4/"
    )


def company_url(creds):
    return f"{root_url(creds)}Company('{creds['BC_COMPANY']}')/"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_bc_probe.py -v`
Expected: PASS, 8 test

- [ ] **Step 5: Verify auth live and that a bad secret leaks nothing**

Run:
```bash
cd "C:/Users/MattiaDaCampo/Documents/orchestrator" && python -c "import sys;sys.path.insert(0,'.claude/skills/zafferano-bc');import bc_probe;c,s=bc_probe.load_credentials();print('fonte:',s);print('token len:',len(bc_probe.get_token(c)))"
```
Expected: stampa la fonte e una lunghezza di token > 500.

Poi, con secret errato:
```bash
cd "C:/Users/MattiaDaCampo/Documents/orchestrator" && BC_TENANT_ID=x BC_CLIENT_ID=y BC_CLIENT_SECRET=NOTAREALSECRET python -c "import sys;sys.path.insert(0,'.claude/skills/zafferano-bc');import bc_probe;c,_=bc_probe.load_credentials();bc_probe.get_token(c)" 2>&1 | grep -c NOTAREALSECRET
```
Expected: `0` — il secret non compare nell'errore.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/zafferano-bc/bc_probe.py tests/test_bc_probe.py
git commit -m "feat(zafferano-bc): credential resolution and BC auth"
```

---

### Task 2: Sottocomandi `list` e `raw`

**Files:**
- Modify: `.claude/skills/zafferano-bc/bc_probe.py`
- Test: `tests/test_bc_probe.py`

**Interfaces:**
- Consumes: `load_credentials`, `get_token`, `root_url`, `company_url` (Task 1)
- Produces:
  - `bc_get(url: str, token: str, params: dict | None = None) -> dict`
  - `list_entity_sets(token: str, creds: dict) -> list[str]`
  - `filter_names(names: list[str], pattern: str | None) -> list[str]`
  - `main(argv: list[str] | None = None) -> int` con subparser `list` e `raw`

- [ ] **Step 1: Write the failing test**

Aggiungi a `tests/test_bc_probe.py`:

```python
def test_filter_names_is_case_insensitive_substring():
    names = ["Articoli", "Price_ListLines", "Listini_prezzi_vendita_righe"]
    assert bc_probe.filter_names(names, "listi") == [
        "Price_ListLines",
        "Listini_prezzi_vendita_righe",
    ]


def test_filter_names_without_pattern_returns_all():
    names = ["A", "B"]
    assert bc_probe.filter_names(names, None) == ["A", "B"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_bc_probe.py -k filter_names -v`
Expected: FAIL — `AttributeError: module 'bc_probe' has no attribute 'filter_names'`

- [ ] **Step 3: Write minimal implementation**

Aggiungi a `bc_probe.py`:

```python
import argparse
import json
import sys


def bc_get(url, token, params=None):
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        params=params,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def list_entity_sets(token, creds):
    """Elenco degli entity set pubblicati.

    Sta alla RADICE /ODataV4/, non sotto Company('...'): sotto Company la
    risposta e' una lista vuota e sembra che il tenant non pubblichi nulla.
    """
    data = bc_get(root_url(creds), token)
    return sorted(item.get("name", "") for item in data.get("value", []))


def filter_names(names, pattern):
    if not pattern:
        return list(names)
    needle = pattern.lower()
    return [n for n in names if needle in n.lower()]
```

E il `main` con i due sottocomandi:

```python
def _build_parser():
    parser = argparse.ArgumentParser(prog="bc_probe", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="entity set pubblicati")
    p_list.add_argument("--grep", help="filtro sottostringa, case-insensitive")
    p_list.add_argument("--json", action="store_true", help="output JSON")

    p_raw = sub.add_parser("raw", help="GET su un percorso OData arbitrario")
    p_raw.add_argument("path", help="percorso dopo /ODataV4/")

    return parser


def main(argv=None):
    args = _build_parser().parse_args(argv)
    try:
        creds, source = load_credentials()
    except CredentialError as exc:
        print(exc, file=sys.stderr)
        return 2
    token = get_token(creds)

    if args.cmd == "list":
        names = filter_names(list_entity_sets(token, creds), args.grep)
        if args.json:
            print(json.dumps(names, ensure_ascii=False, indent=2))
        else:
            for name in names:
                print(name)
            print(f"\n{len(names)} entity set (fonte credenziali: {source})")
        return 0

    if args.cmd == "raw":
        data = bc_get(root_url(creds) + args.path.lstrip("/"), token)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_bc_probe.py -v`
Expected: PASS, 10 test

- [ ] **Step 5: Verify live**

Run:
```bash
python .claude/skills/zafferano-bc/bc_probe.py list --grep listin
```
Expected: elenca fra gli altri `ListiniAcquisto_righe`, `ListiniAcquisto_test`, `Listini_prezzi_vendita_righe`, `Listino_prezzi_di_vendita_Excel`.

Run:
```bash
python .claude/skills/zafferano-bc/bc_probe.py list | tail -1
```
Expected: `231 entity set (fonte credenziali: ...)`. **Annota il numero esatto: serve al Task 5.**

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/zafferano-bc/bc_probe.py tests/test_bc_probe.py
git commit -m "feat(zafferano-bc): list and raw subcommands"
```

---

### Task 3: Sottocomando `fields` (parsing `$metadata`)

**Files:**
- Modify: `.claude/skills/zafferano-bc/bc_probe.py`
- Test: `tests/test_bc_probe.py`

**Interfaces:**
- Consumes: `bc_get`, `root_url`, `_build_parser`, `main` (Task 2)
- Produces:
  - `parse_entity_fields(xml_bytes: bytes) -> dict[str, list[dict]]` — ogni campo e' `{"name": str, "type": str, "nullable": bool}`
  - `fetch_metadata(token: str, creds: dict) -> bytes`
  - `render_table(rows: list[dict], columns: list[str]) -> str`

Nota: `$metadata` pesa circa 4 MB. Va scaricato una volta e riusato, non una volta per entita'.

- [ ] **Step 1: Write the failing test**

Aggiungi a `tests/test_bc_probe.py`:

```python
METADATA_FIXTURE = b"""<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx xmlns:edmx="http://docs.oasis-open.org/odata/ns/edmx" Version="4.0">
 <edmx:DataServices>
  <Schema xmlns="http://docs.oasis-open.org/odata/ns/edm" Namespace="NAV">
   <EntityType Name="Articoli">
    <Key><PropertyRef Name="No"/></Key>
    <Property Name="No" Type="Edm.String" Nullable="false"/>
    <Property Name="Unit_Price" Type="Edm.Decimal" Nullable="true"/>
   </EntityType>
   <EntityType Name="DB_Righe">
    <Property Name="Production_BOM_No" Type="Edm.String" Nullable="false"/>
   </EntityType>
  </Schema>
 </edmx:DataServices>
</edmx:Edmx>
"""


def test_parse_entity_fields_extracts_names_types_nullable():
    parsed = bc_probe.parse_entity_fields(METADATA_FIXTURE)
    assert set(parsed) == {"Articoli", "DB_Righe"}
    assert parsed["Articoli"][0] == {
        "name": "No",
        "type": "Edm.String",
        "nullable": False,
    }
    assert parsed["Articoli"][1]["type"] == "Edm.Decimal"
    assert parsed["Articoli"][1]["nullable"] is True


def test_render_table_aligns_and_keeps_header():
    out = bc_probe.render_table(
        [{"name": "No", "type": "Edm.String"}, {"name": "Unit_Price", "type": "Edm.Decimal"}],
        ["name", "type"],
    )
    lines = out.splitlines()
    assert lines[0].split() == ["name", "type"]
    assert "Unit_Price" in lines[-1]
    assert len(lines[1].strip()) > 0  # riga separatrice
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_bc_probe.py -k "parse_entity_fields or render_table" -v`
Expected: FAIL — `AttributeError: module 'bc_probe' has no attribute 'parse_entity_fields'`

- [ ] **Step 3: Write minimal implementation**

Aggiungi a `bc_probe.py` (l'import va in cima al file):

```python
import xml.etree.ElementTree as ET

EDM_NS = "{http://docs.oasis-open.org/odata/ns/edm}"


def parse_entity_fields(xml_bytes):
    root = ET.fromstring(xml_bytes)
    entities = {}
    for entity_type in root.iter(f"{EDM_NS}EntityType"):
        fields = [
            {
                "name": prop.get("Name"),
                "type": prop.get("Type"),
                "nullable": prop.get("Nullable", "true") == "true",
            }
            for prop in entity_type.findall(f"{EDM_NS}Property")
        ]
        entities[entity_type.get("Name")] = fields
    return entities


def fetch_metadata(token, creds):
    resp = requests.get(
        root_url(creds) + "$metadata",
        headers={"Authorization": f"Bearer {token}"},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.content


def render_table(rows, columns):
    if not rows:
        return "(nessuna riga)"
    widths = {
        c: max(len(c), max(len(str(r.get(c, ""))) for r in rows)) for c in columns
    }
    header = "  ".join(c.ljust(widths[c]) for c in columns).rstrip()
    rule = "  ".join("-" * widths[c] for c in columns).rstrip()
    body = [
        "  ".join(str(r.get(c, "")).ljust(widths[c]) for c in columns).rstrip()
        for r in rows
    ]
    return "\n".join([header, rule, *body])
```

Aggiungi il subparser in `_build_parser`:

```python
    p_fields = sub.add_parser("fields", help="campi di un'entita' da $metadata")
    p_fields.add_argument("entity", help="nome esatto dell'entity set")
    p_fields.add_argument("--grep", help="filtro sottostringa sui nomi campo")
```

E il ramo in `main`, prima di `return 1`:

```python
    if args.cmd == "fields":
        entities = parse_entity_fields(fetch_metadata(token, creds))
        fields = entities.get(args.entity)
        if fields is None:
            close = filter_names(sorted(entities), args.entity)
            print(f"Entita' '{args.entity}' non trovata.", file=sys.stderr)
            if close:
                print(f"Forse cercavi: {', '.join(close[:10])}", file=sys.stderr)
            return 3
        if args.grep:
            needle = args.grep.lower()
            fields = [f for f in fields if needle in f["name"].lower()]
        print(render_table(fields, ["name", "type", "nullable"]))
        print(f"\n{len(fields)} campi in {args.entity}")
        return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_bc_probe.py -v`
Expected: PASS, 13 test

- [ ] **Step 5: Verify live**

Run:
```bash
python .claude/skills/zafferano-bc/bc_probe.py fields Articoli --grep lumen
```
Expected: mostra `NBT_ZAF_Lamp_Lumens`, `NBT_ZAF_Lumens_Light_Source`, `NBT_ZAF_Lumens_Light_Source_S2`.

Run:
```bash
python .claude/skills/zafferano-bc/bc_probe.py fields DB_Righe | tail -1
```
Expected: `23 campi in DB_Righe`

Run:
```bash
python .claude/skills/zafferano-bc/bc_probe.py fields Articolii 2>&1 | head -2
```
Expected: messaggio "non trovata" piu' un suggerimento contenente `Articoli`.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/zafferano-bc/bc_probe.py tests/test_bc_probe.py
git commit -m "feat(zafferano-bc): fields subcommand over \$metadata"
```

---

### Task 4: Sottocomando `query` con paginazione

**Files:**
- Modify: `.claude/skills/zafferano-bc/bc_probe.py`
- Test: `tests/test_bc_probe.py`

**Interfaces:**
- Consumes: `company_url`, `render_table`, `bc_get` (Task 2-3)
- Produces:
  - `build_query_params(filter_expr, select, top) -> dict`
  - `fetch_all(url, token, params, max_rows=None, getter=bc_get) -> list[dict]`

`fetch_all` segue `@odata.nextLink`. Ignorarlo legge solo la prima pagina in silenzio: e' la trappola piu' costosa dell'intera API.

- [ ] **Step 1: Write the failing test**

Aggiungi a `tests/test_bc_probe.py`:

```python
def test_build_query_params_uses_odata_dollar_names():
    params = bc_probe.build_query_params("No eq 'X'", "No,Description", 5)
    assert params == {
        "$filter": "No eq 'X'",
        "$select": "No,Description",
        "$top": 5,
    }


def test_build_query_params_omits_unset_options():
    assert bc_probe.build_query_params(None, None, None) == {}


def test_fetch_all_follows_nextlink_and_drops_params_after_first_page():
    calls = []

    def fake_getter(url, token, params=None):
        calls.append((url, params))
        if url == "start":
            return {"value": [{"n": 1}], "@odata.nextLink": "page2"}
        return {"value": [{"n": 2}]}

    rows = bc_probe.fetch_all("start", "tok", {"$filter": "x"}, getter=fake_getter)
    assert rows == [{"n": 1}, {"n": 2}]
    assert calls[0] == ("start", {"$filter": "x"})
    # nextLink porta gia' la query dentro l'URL: ripassare i params la duplica
    assert calls[1] == ("page2", None)


def test_fetch_all_stops_at_max_rows():
    def fake_getter(url, token, params=None):
        return {"value": [{"n": 1}, {"n": 2}, {"n": 3}], "@odata.nextLink": "more"}

    rows = bc_probe.fetch_all("start", "tok", {}, max_rows=2, getter=fake_getter)
    assert len(rows) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_bc_probe.py -k "build_query_params or fetch_all" -v`
Expected: FAIL — `AttributeError: module 'bc_probe' has no attribute 'build_query_params'`

- [ ] **Step 3: Write minimal implementation**

Aggiungi a `bc_probe.py`:

```python
def build_query_params(filter_expr, select, top):
    params = {}
    if filter_expr:
        params["$filter"] = filter_expr
    if select:
        params["$select"] = select
    if top:
        params["$top"] = top
    return params


def fetch_all(url, token, params, max_rows=None, getter=bc_get):
    """Legge tutte le pagine seguendo @odata.nextLink.

    Il nextLink porta gia' la query string: ripassare params lo duplicherebbe.
    """
    rows = []
    while url:
        data = getter(url, token, params=params)
        rows.extend(data.get("value", []))
        if max_rows is not None and len(rows) >= max_rows:
            return rows[:max_rows]
        url = data.get("@odata.nextLink")
        params = None
    return rows
```

Aggiungi il subparser:

```python
    p_query = sub.add_parser("query", help="legge righe da un'entita'")
    p_query.add_argument("entity")
    p_query.add_argument("--filter", dest="filter_expr", help="espressione $filter OData")
    p_query.add_argument("--select", help="elenco campi separati da virgola")
    p_query.add_argument("--top", type=int, help="ferma la lettura a N righe")
    p_query.add_argument("--json", action="store_true")
```

E il ramo in `main`:

```python
    if args.cmd == "query":
        params = build_query_params(args.filter_expr, args.select, args.top)
        rows = fetch_all(
            company_url(creds) + args.entity, token, params, max_rows=args.top
        )
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))
        else:
            columns = (
                args.select.split(",")
                if args.select
                else list(rows[0])[:8] if rows else []
            )
            print(render_table(rows, columns))
            print(f"\n{len(rows)} righe da {args.entity}")
        return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_bc_probe.py -v`
Expected: PASS, 17 test

- [ ] **Step 5: Verify live**

Run:
```bash
python .claude/skills/zafferano-bc/bc_probe.py query Articoli --select "No,Description,Unit_Price" --top 5
```
Expected: tabella di 5 righe con codici articolo reali. **Annota un codice articolo vero: serve ai Task 6 e 7.**

Run:
```bash
python .claude/skills/zafferano-bc/bc_probe.py query Price_ListLines --filter "Price_List_Code eq '1'" --select "Product_No,Unit_Price" --top 3
```
Expected: 3 righe di listino.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/zafferano-bc/bc_probe.py tests/test_bc_probe.py
git commit -m "feat(zafferano-bc): query subcommand with nextLink pagination"
```

---

### Task 5: `references/entities.md` — catalogo delle entita'

**Files:**
- Create: `.claude/skills/zafferano-bc/references/entities.md`

**Interfaces:**
- Consumes: `bc_probe.py list`, `bc_probe.py fields` (Task 2-3)
- Produces: nessuna interfaccia di codice; documento consumato da SKILL.md

Questo task non ha test unitari: il contenuto si verifica confrontandolo con `$metadata` dal vivo.

- [ ] **Step 1: Estrai l'elenco completo**

```bash
python .claude/skills/zafferano-bc/bc_probe.py list --json > "$TMPDIR/entity_sets.json"
```
(Su questa macchina usa la scratchpad di sessione al posto di `$TMPDIR`.)

- [ ] **Step 2: Scrivi il documento raggruppando per dominio**

Crea `references/entities.md` con questa struttura. I gruppi si assegnano per prefisso, in quest'ordine di precedenza:

1. `PBI_*` e `Power_BI_*` e `powerbifinance` → **Power BI** (viste predisposte per il reporting)
2. `*_Excel` → **Export Excel** (pagine pensate per l'export, spesso duplicano un'entita' operativa)
3. `workflow*`, `salesDocument*`, `purchaseDocument*` → **OData standard / workflow** (API BC di serie, non personalizzazioni)
4. tutto il resto → assegnalo a mano fra: **Anagrafiche**, **Articoli e distinte**, **Listini**, **Vendite**, **Acquisti**, **Movimenti contabili**, **Configurazione**

Per ciascun gruppo: elenco dei nomi, e per le entita' core una riga su cosa contengono.

- [ ] **Step 3: Aggiungi il catalogo campi per le entita' core**

Per queste entita' includi i campi, estratti con `bc_probe.py fields <nome>`:

`Articoli`, `Fornitori`, `Scheda_Fornitore`, `Dati_Clienti`, `Agenti`, `Price_List`, `Price_ListLines`, `Listini_prezzi_vendita_righe`, `ListiniAcquisto_test`, `ListiniAcquisto_righe`, `ListiniAcquisto_righeLines`, `DB_Righe`, `DBAssemblaggio`, `RigheAnalisiVenduto`, `Ordini_di_Vendita`, `Ordini_di_VenditaSalesLines`, `OC_testate`, `ItemLedgerEntries`, `Ubicazioni`, `Collocazioni`, `UM`, `Articoli_Statistici`.

**Regola per le entita' grasse.** `Articoli` ha 210 campi, `Dati_Clienti` 266, `RigheAnalisiVenduto` 208. Un elenco piatto di 266 righe non e' consultabile. Per ogni entita' oltre i 60 campi, raggruppa i campi per tema con un sottotitolo — per `Articoli`: *identita' e descrizioni*, *commerciale e prezzi*, *contabile e gruppi di registrazione*, *attributi prodotto Zafferano* (`NBT_ZAF_*`: sorgente luminosa, watt, lumen, temperatura colore, IP, batteria), *imballo* (i tre livelli `Package_N_*`), *campi filtro* (i `*_Filter` in coda, che non sono dati ma filtri di pagina). Sotto ogni tema, l'elenco dei campi.

- [ ] **Step 4: Verifica il conteggio contro il vivo**

```bash
python .claude/skills/zafferano-bc/bc_probe.py list | tail -1
grep -c '^- `' .claude/skills/zafferano-bc/references/entities.md
```
Expected: il numero di entita' nel documento coincide con quello riportato dal probe (231 al 2026-08-10).

- [ ] **Step 5: Verifica a campione i campi**

Per tre entita' a scelta fra quelle core, confronta il conteggio campi:
```bash
python .claude/skills/zafferano-bc/bc_probe.py fields DB_Righe | tail -1
python .claude/skills/zafferano-bc/bc_probe.py fields DBAssemblaggio | tail -1
python .claude/skills/zafferano-bc/bc_probe.py fields Price_ListLines | tail -1
```
Expected: rispettivamente 23, 17, 33 campi — e gli stessi numeri nel documento. Se divergono, il documento e' sbagliato, non il probe.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/zafferano-bc/references/entities.md
git commit -m "docs(zafferano-bc): entity catalogue from live \$metadata"
```

---

### Task 6: `references/relazioni.md` — la mappa delle giunzioni

**Files:**
- Create: `.claude/skills/zafferano-bc/references/relazioni.md`

**Interfaces:**
- Consumes: `bc_probe.py query` (Task 4), `references/entities.md` (Task 5)
- Produces: documento consumato da SKILL.md

E' il cuore della skill: la domanda vera di un agente non e' "quali entita' esistono" ma "ho un codice articolo, come ricavo tutto quello che si sa su di lui".

- [ ] **Step 1: Scrivi la sezione "chiavi e prefissi"**

Contenuto obbligatorio:

- `Articoli.No` e' il codice articolo, chiave di join universale.
- `Dati_Clienti.No` e' il codice cliente; `Fornitori.No` il codice fornitore.
- Convenzione dei prefissi, che da sola risparmia molta confusione:
  - nome nudo (`No`, `Description`, `Unit_Price`) → campo Business Central standard;
  - `NBT_*` → personalizzazione del partner implementativo;
  - `NBT_ZAF_*` → personalizzazione specifica di Zafferano. Qui stanno gli attributi illuminotecnici di prodotto (`NBT_ZAF_Total_Watt`, `NBT_ZAF_Lamp_Lumens`, `NBT_ZAF_Color_Temperature`, `NBT_ZAF_IP`, `NBT_ZAF_Battery_Type`) e i tre livelli di imballo.
  - i campi in coda che finiscono per `_Filter` non sono dati: sono filtri di pagina, e in `$select` non restituiscono nulla di utile.

- [ ] **Step 2: Scrivi la tabella delle giunzioni**

Ogni riga: da → a, campo esatto, nota. Contenuto obbligatorio:

| Da | A | Giunzione | Nota |
|---|---|---|---|
| `Articoli` | `Price_ListLines` | `Articoli.No` = `Price_ListLines.Product_No` | filtra sempre per `Price_List_Code`, altrimenti prendi tutti i listini insieme |
| `Articoli` | `DB_Righe` | `Articoli.Production_BOM_No` = `DB_Righe.Production_BOM_No` | **non** `Articoli.No` = `DB_Righe.No`: quello e' il componente |
| `Articoli` | `DBAssemblaggio` | `Articoli.No` = `DBAssemblaggio.Parent_Item_No` | `.No` e' il componente, `.Parent_Item_No` il padre |
| `Articoli` | `Fornitori` | `Articoli.Vendor_No` = `Fornitori.No` | fornitore preferenziale, non l'unico storico |
| `Articoli` | `RigheAnalisiVenduto` | `Articoli.No` = `RigheAnalisiVenduto.No` | vedi Step 4: spesso la join non serve |
| `RigheAnalisiVenduto` | `Dati_Clienti` | `.Sell_to_Customer_No` = `Dati_Clienti.No` | esiste anche `Bill_to_Customer_No`, diverso quando fatturi a terzi |

**La riga sulla distinta base e' la piu' importante.** Invertire i due campi non da' errore: restituisce in silenzio l'albero sbagliato. Vale un avviso esplicito nel documento.

- [ ] **Step 3: Documenta i doppioni**

`Price_ListLines` e `Listini_prezzi_vendita_righe` espongono lo stesso identico insieme di 33 campi: sono due pagine pubblicate sulla stessa tabella sottostante. Verificalo prima di scriverlo:

```bash
python .claude/skills/zafferano-bc/bc_probe.py fields Price_ListLines --json > "$TMPDIR/a.json" 2>/dev/null || python .claude/skills/zafferano-bc/bc_probe.py fields Price_ListLines > "$TMPDIR/a.txt"
python .claude/skills/zafferano-bc/bc_probe.py fields Listini_prezzi_vendita_righe > "$TMPDIR/b.txt"
diff "$TMPDIR/a.txt" "$TMPDIR/b.txt" && echo "IDENTICI"
```
Expected: `IDENTICI`. Se differiscono, scrivi la differenza reale invece dell'affermazione.

Segnala anche la famiglia `*_Excel`, che duplica entita' operative con un taglio pensato per l'export.

- [ ] **Step 4: Documenta quando NON fare join**

`RigheAnalisiVenduto` e' denormalizzata: 208 campi che portano gia' dentro gli attributi di prodotto appiattiti (`Brand`, `Collection`, `Family`, `Total_Watt`, `IP`, `Package_1_*`...) e i dati di cliente e spedizione. Per l'analisi del venduto la join ad `Articoli` e a `Dati_Clienti` e' quasi sempre inutile e costosa. Nota anche che qui i campi hanno il nome **senza** prefisso `NBT_ZAF_` (`Total_Watt`, non `NBT_ZAF_Total_Watt`): stesso dato, nome diverso a seconda dell'entita'. E' una trappola concreta per chi copia un `$select` da una query all'altra.

- [ ] **Step 5: Scrivi le ricette, e provale**

Quattro ricette, ciascuna con il comando `bc_probe` che la realizza. Usa il codice articolo vero annotato al Task 4, Step 5.

1. **Tutto sull'articolo X** — scheda, listini in cui compare, distinta, venduto.
2. **Listino completo per codice listino.**
3. **Distinta esplosa di un articolo** — prima leggi `Articoli.Production_BOM_No`, poi filtra `DB_Righe`.
4. **Venduto per articolo e periodo** — da `RigheAnalisiVenduto`, senza join.

Ogni comando va **eseguito davvero** e il conteggio righe riportato nel documento. Una ricetta che non e' stata lanciata non entra nel file.

Esempio per la ricetta 3, da adattare al codice reale:
```bash
python .claude/skills/zafferano-bc/bc_probe.py query Articoli --filter "No eq 'CODICE'" --select "No,Description,Production_BOM_No,Assembly_BOM"
python .claude/skills/zafferano-bc/bc_probe.py query DB_Righe --filter "Production_BOM_No eq 'BOM_TROVATO'" --select "Line_No,No,Description,Quantity_per"
```

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/zafferano-bc/references/relazioni.md
git commit -m "docs(zafferano-bc): join map, prefix conventions, verified recipes"
```

---

### Task 7: `SKILL.md` e verifica d'insieme

**Files:**
- Create: `.claude/skills/zafferano-bc/SKILL.md`
- Modify: `.claude/skills/zafferano-bc/references/relazioni.md` (solo se la verifica finale trova errori)

**Interfaces:**
- Consumes: tutto quanto sopra
- Produces: la skill invocabile

- [ ] **Step 1: Scrivi il frontmatter**

Segui la forma delle altre skill del repo (`.claude/skills/clockify-report/SKILL.md`):

```markdown
---
name: zafferano-bc
description: Use when working with Zafferano's Microsoft Dynamics 365 Business Central — reading articles, price lists (listini), customer/supplier master data (anagrafiche), bills of materials (distinte basi), or sales analysis over OData V4. Covers auth, the published entity sets, how entities join from an article code, and a live probe for querying BC. Triggers on Business Central, BC OData, Articoli, Price_ListLines, listino, anagrafica, distinta base, or when an agent needs an endpoint or field name for Zafferano's BC.
---
```

- [ ] **Step 2: Scrivi il corpo**

Target ~150 righe, in quest'ordine (il primo elemento e' quello che costa piu' tempo a chi non lo sa):

1. **I due URL.** Radice `.../v2.0/{tenant}/{env}/ODataV4/` per service document e `$metadata`; `{radice}Company('Zafferano S.r.l.')/` per i dati. Interrogare il service document sotto `Company('...')` risponde con lista vuota e fa credere che il tenant non pubblichi niente.
2. **Auth**, compatta: client credentials, scope `https://api.businesscentral.dynamics.com/.default`, token 1 ora, variabili `BC_*`. Tenant `75504027-0c82-4005-973f-d2196c2680ff`, env `IT-Prod`, company `Zafferano S.r.l.`.
3. **Trappole**, in ordine di costo:
   - `@odata.nextLink`: chi non pagina legge la prima pagina e non se ne accorge;
   - la distinta base si raggiunge da `Production_BOM_No`, non dal codice articolo;
   - lo stesso attributo cambia nome fra entita' (`NBT_ZAF_Total_Watt` in `Articoli`, `Total_Watt` in `RigheAnalisiVenduto`);
   - nomi di entita' italiani e non deducibili, piu' qualche accento: leggere UTF-8;
   - i campi `*_Filter` non sono dati;
   - in pratica sola lettura.
4. **Orientamento**: le entita' che servono quasi sempre, una riga ciascuna.
5. **Il probe**, con i quattro comandi ed esempi reali.
6. **Quando aprire i reference**: `relazioni.md` per collegare entita' o partire da un codice articolo; `entities.md` per trovare un'entita' o i campi di una in particolare; il probe quando l'entita' non e' in elenco — il catalogo e' una fotografia, `$metadata` e' la verita'.

- [ ] **Step 3: Verifica che la skill sia raggiungibile**

```bash
ls -la "C:/Users/MattiaDaCampo/.claude/skills/zafferano-bc/" 2>&1 | head -3
```
Expected: elenca SKILL.md e references/ tramite la junction. Se la junction non propaga la nuova directory, riportalo — non aggirarlo creando copie.

- [ ] **Step 4: Verifica il probe da fuori Zafferano**

Dimostra che la risoluzione credenziali regge da una directory non-progetto:
```bash
cd "$HOME" && python "C:/Users/MattiaDaCampo/Documents/orchestrator/.claude/skills/zafferano-bc/bc_probe.py" list --grep articoli
```
Expected: elenca `Articoli`, `Articoli_Statistici`, `Articoli_Statistici_Excel`.

- [ ] **Step 5: Verifica che nessun segreto sia finito nei file**

```bash
cd "C:/Users/MattiaDaCampo/Documents/orchestrator" && grep -rniE "client_secret\s*[:=]\s*[\"'][A-Za-z0-9._~-]{8,}" .claude/skills/zafferano-bc/ ; echo "exit=$?"
```
Expected: nessuna riga, `exit=1`.

- [ ] **Step 6: Prova d'uso a freddo**

Rileggi `SKILL.md` come se non sapessi niente di questo BC e rispondi a: *"ho il codice articolo X, dammi descrizione, prezzo di listino 1 e componenti della distinta"*. Se per rispondere devi aprire qualcosa che SKILL.md non nomina, o indovinare un nome di campo, SKILL.md e' incompleto: correggilo.

- [ ] **Step 7: Full test suite e commit**

```bash
python -m pytest tests/ -v
```
Expected: PASS, inclusi i 17 test di `test_bc_probe.py`, e nessuna regressione sui test preesistenti del repo.

```bash
git add .claude/skills/zafferano-bc/
git commit -m "feat(zafferano-bc): SKILL.md entry point, end-to-end verified"
```

---

## Self-Review

**Copertura dello spec:** auth → Task 1; due URL e trappola radice/Company → Task 2 + 7; probe a quattro sottocomandi → Task 2-4; risoluzione credenziali in tre passi con costante isolata → Task 1; nessun segreto nei file ne' negli errori → Task 1 Step 5, Task 7 Step 5; catalogo dal vivo → Task 5; mappa relazionale, prefissi, doppioni, quando non fare join, ricette → Task 6; SKILL.md e divulgazione progressiva → Task 7; verifica da directory non-progetto → Task 7 Step 4; conteggio entita' coerente col service document → Task 5 Step 4.

**Nessun placeholder:** ogni step di codice porta il codice; ogni step di verifica porta comando e output atteso; i due task di documentazione portano il contenuto obbligatorio invece di "scrivi la documentazione".

**Coerenza dei nomi:** `bc_get`, `fetch_all`, `build_query_params`, `render_table`, `parse_entity_fields`, `filter_names`, `load_credentials`, `resolve_credentials`, `choose_env_file`, `root_url`, `company_url` — definiti una volta e usati con lo stesso nome e la stessa firma nei task successivi. `render_table(rows, columns)` ha due argomenti posizionali in Task 3 e viene chiamata con due in Task 4. `fetch_all` accetta `getter` per l'iniezione nei test e usa `bc_get` come default.
