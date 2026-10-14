---
name: no-comments
description: "Periodic comment cleanup on a whole project: parallel read-only auditors, a counted list, bulk apply in a dedicated worktree, proof that no code changed, CI, merge only on Mattia's ok. Keeps only true comments that help (the why, domain rules, contracts, directives); kills narration, history, banners, dead code, stale and false comments. Invoke explicitly with /no-comments [repo|diff|<paths>]."
user-invocable: true
disable-model-invocation: true
---

# No comments

Mattia la lancia ogni 2-3 settimane sui suoi progetti. Lo scopo: **togliere ogni commento inutile, stantio o falso, e tenere solo quelli veri che aiutano chi legge il codice**. Il codice non si tocca mai: si cambiano solo commenti e docstring, e lo si **prova**.

Ispirata a [`pstack/no-comments`](https://github.com/cursor/plugins/blob/main/pstack/skills/no-comments/SKILL.md) (Comment Sicko): odio di principio per i commenti, il dubbio uccide. In più: le regole di protezione del progetto e il metodo a fasi rodato il 14/10/2026 su un progetto vero (343 file, circa 2.800 righe nette tolte, 0 righe di codice cambiate).

## Argomento

- `repo` (default): tutto il repository versionato.
- `diff`: solo i file cambiati dall'ultima pulizia. È l'ultimo commit il cui messaggio contiene «pulizia dei commenti»; se non c'è, il diff è contro il branch di default.
- `<paths>`: solo quei percorsi.

## Regole ferme

- **Solo commenti e docstring.** Niente codice, niente rinomine, niente refactor. Il codice sospetto trovato strada facendo (workaround, soppressioni di lint che coprono bug veri, comportamenti sorprendenti spiegati in prosa) va nella lista **MUST KILL** del report: non si corregge qui.
- **Mai nel checkout principale.** Si lavora in un worktree dedicato con un branch `pulizia-commenti-<data>` dal branch di default locale. In T3 si usa `t3_thread_launch` con `workspaceStrategy: worktree`; altrimenti `git worktree add`.
- Auditor e applicatori **non fanno operazioni git**. Commit, push e merge li fa chi orchestra, e merge e push solo col sì di Mattia in quel momento.
- **Niente issue sul tracker** per la pulizia stessa, salvo che Mattia la chieda. I MUST KILL invece si accodano all'issue di debito tecnico del progetto, se esiste, oppure si propongono.
- I comandi distruttivi (`rm -rf`, `git worktree remove`, `branch -D`) li blocca il gate: per la pulizia finale si consegna a Mattia uno script PowerShell commentato.

## Cosa muore

- Commento che ripete il codice: nome, tipo, operazione ovvia, «docstring» che parafrasa la firma.
- **Storia e changelog**: «prima era X, ora Y», «corretto dopo…», «sostituiti, non affiancati», «era ricopiata in dieci liste», date di modifica. La storia sta in git.
- Banner e separatori decorativi (`# ----`, `// ====`, `/* === Sezione === */`), righe `#` vuote di riempimento.
- Codice commentato.
- **Commenti falsi o stantii**: descrivono un comportamento che il codice non ha più. Si cancellano, oppure si riscrivono veri se il perché resta valido. Non si lascia mai un commento che contraddice il codice.
- Prosa verbosa: si **accorcia** tenendo solo il perché. Non si lucida un alibi: una giustificazione lunga senza un'eccezione vera sotto muore, e il simbolo va tra i MUST KILL.
- Doppioni fra file gemelli: si tiene una copia sola, nel posto dove il lettore la cerca. La deduplicazione fra file è più rischiosa, quindi si fa in un giro a parte e solo sulle voci sicure.
- TODO senza proprietario né issue: si elencano a parte e non si contano.

## Cosa sopravvive (l'unico guinzaglio)

1. **Il perché non ovvio**: un vincolo, una scelta, un numero misurato, un incidente datato che spiega il codice.
2. **I meccanismi di dominio** che non si deducono dal codice. Ogni progetto li elenca nel suo `CLAUDE.md`/`AGENTS.md`, che gli auditor **leggono per primi**. Esempi tipici: come si calcolano gli importi, multi-tenant e RLS, finestre temporali degli import, viste aggregate in sola lettura, GDPR, audit append-only, denaro come stringa.
3. **Riferimenti** a issue, RFC e decisioni (`ABC-123`, `decisions.md` o ADR, link) che spiegano un vincolo che il codice non può esprimere.
4. **Garanzie con il test citato**, e gli **avvertimenti di copertura** («nessun test copre questa riga: sostituirla lascerebbe la suite verde»). Il 14/10 ne era stato tolto uno per sbaglio ed è stato rimesso.
5. **Contratti**: docstring pubbliche di API, e docstring di rotta e di schema che finiscono in un contratto generato (OpenAPI). Quel file deve restare **identico**.
6. **Direttive**: `noqa`, `type: ignore`, `eslint-disable`, `@ts-expect-error`, `@ts-ignore`, `# pragma`, `prettier-ignore`, `"use client"`, `istanbul`, le shebang e gli header di licenza. Una soppressione che copre un bug vero non si tocca qui: va tra i MUST KILL.
7. **Comportamento imposto da fuori** (vendor, piattaforma, protocollo, libreria) che non possiamo cambiare. Una sorpresa nel **nostro** codice invece non è un'eccezione: il commento muore e il simbolo va tra i MUST KILL (rinomina, estrai, tipizza).
8. Commenti JSX o markup su cui un test fa affidamento.

`IMPORTANT`, `non togliere`, `troppo rischioso` sono un indizio, non una prova. Si legge il codice vicino. Se l'affermazione è vera oggi e rientra nel guinzaglio, sopravvive. Altrimenti muore.

**In fase di audit il dubbio non si conta**: va nella lista «dubbi» e non si applica. Applicando, una voce il cui testo non torna si salta.

## Fasi

### 1. Preparazione
- Leggi `CLAUDE.md`/`AGENTS.md` del progetto: elenco dei meccanismi protetti, limiti di riga (ruff, eslint, prettier), comandi di lint, typecheck, test e CI.
- Crea il worktree e il branch. Dividi lo scope in **perimetri** di dimensione simile: 6-10 su un repo medio, per esempio servizi backend, resto del backend, test, migrazioni e script, componenti, lib, app in due metà. Un perimetro troppo grande per essere letto tutto va spezzato.
- Prepara la cartella di lavoro **fuori dal repo** (es. `~/.t3/no-comments-audit/` o `%TEMP%`): una lista per perimetro e il brief. Nel repo non finisce niente.

### 2. Audit, in sola lettura e in parallelo
Lancia un auditor per perimetro, in parallelo, con `references/brief.md` (sezione Audit). Ognuno legge **tutti** i file del suo perimetro, senza campionare, e scrive la lista `file:righe | RIMUOVI o ACCORCIA → testo | righe nette | motivo`, con i dubbi a parte. Poi somma i numeri.

Mostra a Mattia il totale: righe nette sicure, divise per perimetro e fra RIMUOVI e ACCORCIA, e quanti dubbi. Chiedi se applicare. Una soglia concordata va bene (il 14/10 era «più di 150 righe»): sotto la soglia non vale il giro.

### 3. Applicazione
Lancia un applicatore per perimetro, con `references/brief.md` (sezione Applicazione), dentro un contesto che **può scrivere in massa**. Il 14/10 il controllo dei permessi ha fermato l'applicazione in blocco a metà. Serve un thread o worker in `full-access` nel worktree, oppure un subagent che erediti i permessi giusti. Ogni applicatore:
- trova ogni commento **dal contenuto e non dal numero di riga**, che scade appena qualcuno tocca il file;
- tocca solo il suo perimetro;
- non lascia un corpo vuoto (servono `pass`/`...`), né commenti orfani o spezzati.

### 4. Prova che il codice non è cambiato
Lancia `python -I scripts/verify_comments_only.py <worktree> [base]`. Lo script confronta tutto il diff del worktree contro la base:
- `.py` con l'albero sintattico, docstring escluse;
- `.ts/.tsx/.js/.mjs` con il testo senza `//`, `/* */` e `{/* */}`;
- `.sh` con le righe senza i commenti interi.

**Ogni file segnalato si ispeziona a mano.** Il 14/10 un controllo così ha preso un agente che aveva cancellato una riga di codice JSX insieme al commento.

Sulla pulizia completa del 14/10 lo script dà 342 file identici e 0 da ispezionare, e una riga di codice tolta di proposito la segnala. I suoi limiti sono scritti nella sua docstring: le regex con `//` dentro, e i tipi di file che non conosce, che elenca come «non verificabile».

### 5. Formato e controlli
- Lancia il formattatore del progetto (`ruff format`, prettier) e il linter. Le righe di commento **accorciate o riscritte** sono quelle che sforano il limite di lunghezza: il 14/10 la CI ne ha bocciate 22 oltre i 100 caratteri, più 12 file da riformattare.
- Rilancia la verifica della fase 4 dopo il formattatore.
- Poi typecheck, test e la rigenerazione dei contratti in modalità check (es. `export_openapi.py --check`).
- Infine la CI completa del progetto. Se gira da remoto sul ramo pushato, pusha prima il ramo; se salta le aree non toccate, sul risultato del merge lanciala completa.

### 6. Rilettura dell'orchestratore
Leggi il diff vero. Cerca a campione, a occhio, quello che le macchine non vedono: un perché tolto, un avvertimento di copertura tolto, un riferimento a un'issue tolto, un commento riscritto che ora dice una cosa falsa. Rimetti quello che rientra nel guinzaglio. Non rimettere niente «per sicurezza».

### 7. Merge, push, pulizia
Col sì di Mattia: merge `--no-ff` nel default locale, poi CI sul risultato, poi push. Dopo, cancella il ramo remoto e consegna lo script per rimuovere worktree e ramo locale.

## Report a Mattia

Breve:
- file toccati e `git diff --shortstat` (righe nette);
- esito della verifica «solo commenti» (0 file diversi, oppure quali, ispezionati e perché vanno bene);
- esito di formato, lint, typecheck, test e CI;
- voci saltate o rimesse, e perché;
- dubbi lasciati;
- **MUST KILL**: una riga per simbolo, con file, cosa c'è che non va e la correzione suggerita (rinomina, estrai, tipizza, togli il workaround). Si accodano all'issue di debito tecnico;
- quello che resta fuori, per esempio un perimetro non applicato o la deduplicazione fra file rimandata.
