# Changelog

Tutti i cambiamenti significativi a questo progetto saranno documentati in questo file.

Il formato è basato su [Keep a Changelog](https://keepachangelog.com/it/1.0.0/),
e questo progetto aderisce a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Pianificazione per supporto Drag & Drop dei file.

## [1.2.5] - 2026-04-20

- Fix: Aggiunta la distruzione mirata dei link prima della pulizia del *Garbage Collector*. Vengono rimossi i link (mailto:) relativi agli indirizzi email censurati.

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
