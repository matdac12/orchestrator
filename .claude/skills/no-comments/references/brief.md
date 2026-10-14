# Brief per auditor e applicatori di /no-comments

Chi orchestra copia la sezione giusta nel prompt di ogni subagent. Riempie `<worktree>`, `<perimetro>`, `<file di output>` e l'elenco dei meccanismi protetti del progetto, preso da `CLAUDE.md`/`AGENTS.md`.

---

## Audit (sola lettura)

Worktree: `<worktree>`. Perimetro: `<perimetro>`. Output: `<file di output>`, fuori dal repo.

**Non modificare nessun file del repo**, e non fare operazioni git. Scrivi solo il tuo file di output.

Prima leggi `CLAUDE.md`/`AGENTS.md` del progetto. Poi leggi **tutti** i file del perimetro, riga per riga nei commenti, senza campionare. Se il perimetro è troppo grande, dillo e riporta la copertura reale.

**Da contare (sicuro):**
- commento che ripete il codice (nome, tipo, operazione ovvia, docstring che parafrasa la firma): RIMUOVI;
- storia e changelog («era X, ora Y», «corretto dopo…», date di modifica) senza un perché ancora valido: RIMUOVI, oppure ACCORCIA tenendo solo il perché;
- banner e separatori decorativi, righe `#` vuote di riempimento: RIMUOVI;
- codice commentato: RIMUOVI;
- commento falso o stantio (contraddice il codice di oggi): RIMUOVI, oppure ACCORCIA → testo vero;
- prosa verbosa: ACCORCIA → testo proposto. Conta solo le righe nette risparmiate;
- doppioni fra file gemelli: elencali **a parte**, come «deduplicazione», con quale copia tenere.

**Mai contare, mai proporre:**
- i meccanismi di dominio del progetto: `<elenco da CLAUDE.md>`;
- un perché non ovvio, un numero misurato, un incidente datato;
- riferimenti a issue, RFC e `decisions.md`;
- garanzie con il test citato, e avvertimenti di copertura («nessun test copre…»);
- docstring di contratto: API pubbliche, rotte, schemi che generano OpenAPI;
- direttive (`noqa`, `type: ignore`, `eslint-disable`, `@ts-*`, `# pragma`, `prettier-ignore`, `"use client"`, shebang, licenze);
- comportamento imposto da una dipendenza esterna;
- commenti su cui un test fa affidamento.

**Il dubbio non è sicuro**: mettilo nella lista «dubbi».

**MUST KILL:** se un commento giustifica un workaround o una sorpresa nel **nostro** codice, oppure una soppressione copre un bug vero, il commento si conta come RIMUOVI. Il simbolo va nella lista MUST KILL, con una riga: cosa non va e la correzione suggerita. Non scrivere codice.

**Output nel file**, ordinato per file, con le righe del file **attuale**:
```
file:riga_inizio-riga_fine | RIMUOVI | netto | motivo
file:riga | ACCORCIA → «testo proposto» | netto | motivo
```
Poi tre sezioni: `## Dubbi`, `## Deduplicazione`, `## MUST KILL`.

**Risposta finale** (al massimo 200 parole):
- righe di commento totali nel perimetro, e file letti su file totali;
- **righe nette sicure** (un numero), divise fra RIMUOVI e ACCORCIA;
- i 3 file con il guadagno maggiore;
- quanti dubbi e quanti MUST KILL.

Niente stime vaghe: il numero è quello che risulta dalla lista.

---

## Applicazione

Worktree: `<worktree>`. Perimetro: `<perimetro>`. Lista: `<file di output>`.

Ora puoi **modificare i file del tuo perimetro, e solo quelli**. Altri agenti lavorano in parallelo nello stesso worktree.

- Applica solo le voci RIMUOVI e ACCORCIA della lista. Dubbi, deduplicazione e MUST KILL non si toccano, e non si aggiungono voci nuove.
- **Trova ogni commento dal contenuto, non dal numero di riga.** Prima di ogni modifica ricontrolla il testo attuale. Se non coincide, o se il motivo non vale più, salta e riportalo.
- Cambia **solo** commenti e docstring. Non toccare direttive, docstring di contratto, codice eseguibile né markup.
- Se togli l'unica docstring di un corpo, metti `pass` o `...`. Non lasciare commenti orfani o spezzati, né un file che non compila.
- Il testo nuovo delle voci ACCORCIA rispetta il limite di riga del progetto: va a capo, e non supera i 100 caratteri se il progetto ha quel limite.
- Non fare commit, stash, checkout né altre operazioni git.
- **Verifica:**
  - `.py`: `python -I -m py_compile <file>`;
  - `.ts/.tsx`: eslint o `tsc --noEmit` sui file toccati, se `node_modules` c'è; altrimenti dillo;
  - `.sh`: `bash -n`.

**Risposta finale** (al massimo 120 parole): righe effettivamente tolte e aggiunte (`git diff --numstat -- <perimetro>`), voci saltate e perché, esito delle verifiche.
