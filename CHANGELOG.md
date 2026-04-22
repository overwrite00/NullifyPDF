# Changelog

Tutti i cambiamenti significativi a questo progetto saranno documentati in questo file.

Il formato è basato su [Keep a Changelog](https://keepachangelog.com/it/1.0.0/),
e questo progetto aderisce a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.4.0] - 2026-04-22

### Aggiunto

- **Nuovo Layout GUI**: Introdotta Sidebar laterale per massimizzare lo spazio dell'anteprima PDF.
- **Navigazione Avanzata**: Aggiunto navigatore di pagine con funzione "Jump to Page" (salto diretto inserendo il numero).
- **Persistenza Dizionari**: Blocklist e Allowlist ora vengono salvate permanentemente in `~/.nullifypdf/` su Linux e su Windows nella cartella del profilo dell'utente.
- **Pulsante Exit**: Aggiunta chiusura sicura dell'applicazione dalla sidebar.

### Corretto

- **Anti-Stacking**: Risolto il bug delle annotazioni sovrapposte; l'AI ora rileva se un'area è già censurata.
- **Deep Clean**: La rimozione manuale ora cancella tutti i livelli di censura sovrapposti nello stesso punto.
- **HighDPI Fix**: Logo e icone ora sono nitidi su monitor 4K/Retina grazie a `ctk.CTkImage`.
- **Mutua Esclusività**: Risolto conflitto tra liste; una parola non può più essere contemporaneamente in Blocklist e Allowlist.
- **AttributeError**: Risolto crash al rilascio del mouse se il click iniziale avveniva fuori dal canvas.

### Variato

- Ottimizzata la pulizia del testo estratto (rimozione punteggiatura e normalizzazione spazi) per migliorare il match dei dizionari.

## [1.3.0] - 2026-04-21

### Added

- **AI Engine Integration**: Implementazione di Microsoft Presidio e spaCy per il riconoscimento automatico di entità sensibili (PERSON, LOCATION, IBAN, ecc.).
- **Multilingual Support**: Introdotta la possibilità di selezionare il modello linguistico (EN, IT o entrambi) per la scansione.
- **Smart Dictionaries**: Nuova gestione filtri con **Blocklist** (termini da censurare sempre) e **Allowlist** (termini da ignorare).
- **Interactive Review System**: Possibilità di rimuovere una censura pianificata cliccandoci sopra direttamente nel canvas.
- **Clear All**: Pulsante per eliminare tutte le annotazioni di censura pianificate in un colpo solo.
- **Child Window Icons**: Le finestre "About" e "Dictionary" ora ereditano correttamente l'icona scudo dall'applicazione principale.

### Changed

- **Deferred Redaction**: La censura è ora un processo "differito": viene pianificata graficamente e applicata in modo distruttivo solo durante l'Export.
- **Model Optimization**: Passaggio ai modelli spaCy `_md` (medium) per ridurre il peso dell'eseguibile mantenendo alta precisione.
- **Build Automation**: Aggiornamento del workflow GitHub Actions per includere le dipendenze NLP e i modelli linguistici nelle release.

### Fixed

- **Unicode/Emoji Support**: Risolto il crash durante l'estrazione della versione causato dalla presenza di emoji nel codice sorgente.
- **Linux Environment Variables**: Corretto il passaggio della variabile di versione negli script di packaging per Ubuntu.

## [1.2.5] - 2026-04-20

### Fixed

- Aggiunta la distruzione mirata dei link prima della pulizia del *Garbage Collector*. Vengono rimossi i link (mailto:) relativi agli indirizzi email censurati.

## [1.2.0] - 2026-04-20

### Added

- Finestra "About" informativa con centratura dinamica rispetto alla finestra principale.
- Icona scudo centrata millimetricamente tramite coordinate assolute.
- Clipping delle coordinate per impedire crash durante la selezione manuale fuori dai bordi.

### Fixed

- Corretto il bug del "MouseWheel hijacking": lo scrolling è ora attivo solo quando il cursore è sopra il Canvas del PDF.
- Inizializzazione delle variabili grafiche per evitare errori al ridimensionamento della finestra a documento vuoto.

### Changed

- Ottimizzazione del layout della toolbar per migliorare la leggibilità su monitor piccoli.

## [1.1.0] - 2026-04-18

### Added

- Script `PDF_Checker.py` per l'analisi forense post-processamento.
- Funzionalità di Garbage Collection livello 4 e pulizia metadati profonda durante il salvataggio.

## [1.0.0] - 2026-04-15

### Added

- Rilascio iniziale di NullifyPDF con supporto per anonimizzazione automatica (Regex) e manuale.
- Script di setup cross-platform `setup_env.py`.
