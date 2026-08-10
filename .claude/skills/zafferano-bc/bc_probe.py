#!/usr/bin/env python3
"""
Probe OData V4 per il Business Central di Zafferano.

Sottocomandi: list, fields, query, raw.  Vedi SKILL.md.

Le credenziali si risolvono in ordine: variabili d'ambiente BC_*, poi un .env
risalendo dalla directory corrente, poi i percorsi noti in KNOWN_ENV_PATHS.
Il segreto non viene mai stampato, nemmeno in caso di errore.
"""

import argparse
import difflib
import json
import os
import sys
import xml.etree.ElementTree as ET
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

EDM_NS = "{http://docs.oasis-open.org/odata/ns/edm}"


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
    """Scarica $metadata (circa 4 MB). Una volta sola, poi si riusa."""
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


def suggest_names(needle, names, limit=8):
    """Suggerimenti per un nome sbagliato: prima i simili, poi le sottostringhe.

    La sola sottostringa non basta: un refuso come 'Articolii' non e'
    sottostringa di niente e lascerebbe l'utente senza indizi.
    """
    close = difflib.get_close_matches(needle, names, n=limit, cutoff=0.6)
    substring = [n for n in filter_names(names, needle) if n not in close]
    return (close + substring)[:limit]


def _build_parser():
    parser = argparse.ArgumentParser(prog="bc_probe", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="entity set pubblicati")
    p_list.add_argument("--grep", help="filtro sottostringa, case-insensitive")
    p_list.add_argument("--json", action="store_true", help="output JSON")

    p_fields = sub.add_parser("fields", help="campi di un'entita' da $metadata")
    p_fields.add_argument("entity", help="nome esatto dell'entity set")
    p_fields.add_argument("--grep", help="filtro sottostringa sui nomi campo")

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

    if args.cmd == "fields":
        entities = parse_entity_fields(fetch_metadata(token, creds))
        fields = entities.get(args.entity)
        if fields is None:
            close = suggest_names(args.entity, sorted(entities))
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

    if args.cmd == "raw":
        data = bc_get(root_url(creds) + args.path.lstrip("/"), token)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
