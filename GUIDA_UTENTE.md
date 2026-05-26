# 📖 Guida Pratica all'uso di NullifyPDF

Benvenuto nella guida operativa di NullifyPDF. Questa guida ti accompagnerà passo dopo passo per proteggere i tuoi dati sensibili in modo semplice e sicuro.

---

## 🟢 Passo 1: Caricare il documento

1. Clicca sul pulsante blu **"Apri PDF"** in alto a sinistra.
2. Seleziona il file dal tuo computer.
3. Il documento apparirà nell'area centrale. Puoi scorrere le pagine con il mouse o usare le frecce in alto a destra.

## 🧠 Passo 2: Configurare l'Intelligenza Artificiale

Prima di iniziare, seleziona la lingua del documento nella sidebar:

- **IT**: Per documenti in italiano.
- **EN**: Per documenti in inglese.
- **BOTH**: Se il testo contiene entrambe le lingue.

## 🔴 Passo 3: Censura Automatica

Clicca sul pulsante **"Auto Redact (AI)"**. Il programma cercherà e coprirà automaticamente:

- Nomi e Cognomi
- Indirizzi e Città
- Email e Numeri di Telefono
- IBAN, Carte di Credito e Indirizzi Crypto

## 🖱️ Passo 4: Controllo e Correzione Manuale

Nessuna macchina è perfetta. Puoi intervenire così:

- **Aggiungere una censura:** Disegna un rettangolo con il mouse sopra il testo da nascondere.
- **Rimuovere una censura:** Fai un singolo **click** sulla macchia nera. La censura sparirà e il programma imparerà a ignorare quella parola.
- **Zoom:** Usa i tasti **+ / -** o tieni premuto `CTRL` + Rotellina del mouse per vedere meglio il testo piccolo.

## 🖼️ Passo 5: Nascondere Immagini e Foto

Se vuoi eliminare loghi, firme o foto:

1. Attiva l'interruttore **"Oscura Immagini"**.
2. Clicca di nuovo su **"Auto Redact (AI)"**.
3. Le immagini verranno sostituite da un segnaposto grigio professionale.

## 💾 Passo 6: Esportare il file sicuro

Quando hai finito:

1. Clicca su **"Esporta PDF Sicuro"**.
2. Scegli il nome del file e dove salvarlo.
3. Il nuovo file è ora "sanificato": i dati sotto le macchie nere sono stati distrutti fisicamente e sono irrecuperabili.

---

## 🔧 Gestione Dizionari Persistenti

I tuoi dizionari (Blocklist e Allowlist) vengono salvati automaticamente:

- **Windows**: `C:\Users\<tuonome>\.nullifypdf\`
- **macOS/Linux**: `~/.nullifypdf/`

Dentro questa cartella troverai:
- `blocklist.txt`: Parole che saranno sempre censurate
- `allowlist.txt`: Parole che saranno sempre ignorate dall'AI
- `logs/`: File di log per diagnostica

**⚠️ Nota Importante**: Una parola non può essere contemporaneamente in Blocklist E Allowlist (mutua esclusività).

---

## 🐛 Troubleshooting

### L'App si blocca durante l'AI Scan su PDF grandi
**Causa**: L'estrazione testo da PDF grandi può richiedere tempo.
**Soluzione**: 
- L'app non è bloccata, è solo che il worker thread sta elaborando le pagine
- Attendere che la barra di progresso raggiunga il 100%
- Su PDF > 500 pagine, può richiedere 30-60 secondi

### Crash durante l'Export
**Causa**: Possibili problemi di memoria o file corrotto.
**Soluzione**:
1. Chiudi e riapri l'app
2. Carica il PDF di nuovo
3. Prova di nuovo l'export

Se il problema persiste, controlla i **log file** (vedi sezione "Debug Mode" sotto).

### L'AI non riconosce il mio testo
**Causa**: Lingua selezionata sbagliata o testo in immagini (scansioni).
**Soluzione**:
- Assicurati di aver selezionato la lingua giusta (IT/EN/BOTH)
- Se il PDF è una scansione (fotografia), attiva **"Oscura Immagini"** per censurare l'intera foto
- L'AI analizza solo testo digitale, non OCR

### Permessi file rifiutati su Windows
**Causa**: Il file è bloccato da un processo o permessi insufficienti.
**Soluzione**:
1. Chiudi il file in altri programmi (Word, Adobe Reader, ecc.)
2. Assicurati di avere permessi di scrittura sulla cartella di destinazione
3. Prova a salvare in una cartella diversa (es. Desktop)

---

## 🔍 Debug Mode (Avanzato)

Se riscontri problemi e vuoi aiutare lo sviluppo, puoi abilitare la modalità debug:

### Windows (PowerShell)
```powershell
$env:NULLIFYPDF_DEBUG = "true"
python NullifyPDF.py
```

### macOS/Linux (Bash)
```bash
export NULLIFYPDF_DEBUG=true
python3.12 NullifyPDF.py
```

**Effetto**: Il programma creerà log più dettagliati con stacktrace completi in:
- `~/.nullifypdf/logs/nullifypdf.log`

Puoi consultare questo file per diagnosticare problemi. Se riscontri un crash, questo log sarà utile per segnalare il bug su GitHub.

---

## 📋 File di Log

NullifyPDF crea automaticamente log file per tracciare l'attività:

**Posizione Log**:
- **Windows**: `C:\Users\<tuonome>\.nullifypdf\logs\nullifypdf.log`
- **macOS/Linux**: `~/.nullifypdf/logs/nullifypdf.log`

**Contenuto Log**:
- Timestamp di ogni azione (caricamento, AI scan, export)
- Errori e avvisi con stacktrace completo
- Informazioni di debug (se DEBUG mode abilitato)

**Pulizia Log**: I log file vengono automaticamente ruotati quando raggiungono 5 MB (max 3 backup).

---

## ✅ Best Practice

1. **Backup Originale**: Conserva sempre una copia del PDF originale prima di usare NullifyPDF.
2. **Test su Copia**: Testa il processo su una copia prima di processare il documento ufficiale.
3. **Verifica Export**: Apri il PDF esportato per verificare che le censure siano state applicate correttamente.
4. **Linguaggio Corretto**: Seleziona sempre la lingua esatta del tuo documento (non usare BOTH se non necessario).
5. **Allowlist Attentamente**: Aggiungi a Allowlist solo parole che SICURAMENTE non sono sensibili.

---
