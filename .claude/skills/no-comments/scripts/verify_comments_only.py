"""Prova che il diff di un worktree cambia solo commenti e docstring (sola lettura).

Uso:  python -I verify_comments_only.py <worktree> [base]     (base di default: main)

Confronta ogni file cambiato fra `base` e la copia su disco del worktree (commit del ramo
compresi, modifiche non committate comprese):
  .py                         albero sintattico, docstring escluse
  .ts .tsx .js .jsx .mjs .cjs testo senza //, /* */ e {/* */}, spazi normalizzati
  .css .scss                  testo senza /* */, spazi normalizzati
  .sh .bash                   righe senza i commenti interi, spazi normalizzati
Gli altri tipi vengono elencati come «non verificabile» e si guardano a mano.

Esce con 1 se c'è anche un solo file da ispezionare. Limiti noti: una regex che contiene
`//` o `/*` viene trattata come un commento, quindi una riga di codice cancellata dopo
quella regex, sulla stessa riga, sfuggirebbe; un apostrofo nel testo JSX che trova un altro
apice sulla stessa riga sembra una stringa (falso positivo). Un file segnalato si chiarisce
leggendo il suo diff; il controllo a campione dell'orchestratore resta.
"""

import ast
import re
import subprocess
import sys

JS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
CSS = (".css", ".scss")
SH = (".sh", ".bash")


def git(wt: str, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", wt, *args], capture_output=True, text=True, encoding="utf-8", check=True
    ).stdout


def py_norm(src: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(getattr(body[0], "value", None), ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body = body[1:]
        # Un modulo o un corpo rimasto senza docstring equivale a `pass`.
        node.body = body or [ast.Pass()]
    return ast.dump(tree)


def strip_c_like(src: str, line_comments: bool) -> str:
    out: list[str] = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c in "'\"`":
            j = i + 1
            while j < n and src[j] != c and (c == "`" or src[j] != "\n"):
                j += 2 if src[j] == "\\" else 1
            if j < n and src[j] == "\n":
                # Apice senza chiusura sulla riga: è un apostrofo nel testo JSX
                # (`l'Invio`), non l'inizio di una stringa.
                out.append(c)
                i += 1
                continue
            out.append(src[i : j + 1])
            i = j + 1
        elif line_comments and src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
        else:
            out.append(c)
            i += 1
    text = "".join(out)
    if line_comments:
        # `{/* commento */}` in JSX lascia `{}`: si toglie da tutti e due i lati.
        text = re.sub(r"\{\s*\}", "", text)
    return re.sub(r"\s+", " ", text).strip()


def sh_norm(src: str) -> list[str]:
    return [
        re.sub(r"\s+", " ", line).strip()
        for line in src.splitlines()
        if line.strip() and (not line.lstrip().startswith("#") or line.startswith("#!"))
    ]


def same(path: str, old: str, new: str) -> bool | None:
    if path.endswith(".py"):
        return py_norm(old) == py_norm(new)
    if path.endswith(JS):
        return strip_c_like(old, True) == strip_c_like(new, True)
    if path.endswith(CSS):
        return strip_c_like(old, False) == strip_c_like(new, False)
    if path.endswith(SH):
        return sh_norm(old) == sh_norm(new)
    return None


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    wt = sys.argv[1]
    base = sys.argv[2] if len(sys.argv) > 2 else "main"
    changed = git(wt, "diff", "--name-only", base).split("\n")
    ok, todo = 0, []
    for path in filter(None, changed):
        try:
            old = git(wt, "show", f"{base}:{path}")
        except subprocess.CalledProcessError:
            todo.append((path, "nuovo: non esiste in base"))
            continue
        try:
            with open(f"{wt}/{path}", encoding="utf-8") as f:
                new = f.read()
        except FileNotFoundError:
            todo.append((path, "cancellato"))
            continue
        try:
            verdict = same(path, old, new)
        except SyntaxError as e:
            todo.append((path, f"SyntaxError: {e}"))
            continue
        if verdict is None:
            todo.append((path, "tipo non verificabile"))
        elif verdict:
            ok += 1
        else:
            todo.append((path, "CODICE DIVERSO"))
    print(f"base {base}: {ok} file identici a meno di commenti, {len(todo)} da ispezionare")
    for path, why in todo:
        print(f"  {path}: {why}")
    return 1 if todo else 0


if __name__ == "__main__":
    sys.exit(main())
