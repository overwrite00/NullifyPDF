"""In-app user guide (Italian) and tooltips for every GUI element (Qt).

The guide is opened from the "Guida" button or with F1. Tooltips are applied
by :func:`apply_tooltips`, which looks widgets up by their visible text or
object name; a test checks that no widget of the main window or of the
dialogs is left without one.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# --------------------------------------------------------------------------
# Tooltips
# --------------------------------------------------------------------------

# Exact visible text (or object name) -> tooltip.
TOOLTIPS: Dict[str, str] = {
    # Sidebar
    "Apri PDF": "Apre un file PDF da elaborare. Puoi anche trascinarlo sulla finestra.",
    "Lingua dei documenti: italiano": "NullifyPDF analizza documenti in italiano. Il modello italiano viene scaricato, dopo il tuo consenso, al primo utilizzo.",
    "Oscura Immagini": "Oscura anche tutte le immagini della pagina (loghi, firme, foto) quando applichi Auto Redact.",
    "OCR PDF scansionati": "Legge con l'OCR le pagine scansionate e le immagini incorporate, così anche il testo nelle immagini viene analizzato.",
    "Mostra suggerimenti": "Contorna in arancione, nell'anteprima, i suggerimenti ancora da rivedere. Servono solo a video: non finiscono nel file esportato.",
    "Profilo documenti sanitari": "Cerca anche date di nascita, numero tessera sanitaria, ricetta e codici di esenzione, e propone firme e timbri. I casi incerti diventano suggerimenti invece di essere scartati.",
    "Maschera larghezza testo rimosso": "Arrotonda lo spazio lasciato dal testo rimosso, che altrimenti ne rivela la larghezza. Può spostare di poco il testo seguente.",
    "Dizionari": "Modifica le parole da censurare sempre (blocklist) e da non censurare mai (allowlist), con scadenza.",
    "Modelli locali": "Mostra i modelli locali candidati, la licenza, la copertura e lo stato di verifica. Il download richiede un manifest con revisione e SHA-256.",
    "model_settings": "Gestisce il catalogo curato dei modelli locali. I modelli producono solo suggerimenti e non vengono scaricati senza consenso.",
    "model_list": "Elenco curato dei modelli locali e del loro stato di verifica.",
    "model_details": "Dettagli del modello selezionato, inclusi licenza, runtime, lingue e copertura dichiarata.",
    "model_download": "Scarica un modello solo quando l'applicazione ne ha verificato manifest, revisione e SHA-256.",
    "Auto Redact": "Analizza il documento e segna i dati personali da censurare. Nulla viene cancellato finché non esporti.",
    "Rivedi suggerimenti": "Apre l'elenco dei rilevamenti incerti per decidere uno per uno se censurarli.",
    "Pulisci Pagina": "Rimuove tutte le censure segnate sulla pagina corrente.",
    "Esporta PDF": "Crea il PDF finale: rimozione irreversibile oppure pseudonimizzazione reversibile. Il file viene pulito e verificato.",
    "Ricostruisci PDF": "Rimette i valori originali in un PDF pseudonimizzato usando la sua mappa di ripristino e la password (o la chiave di recupero).",
    "Elimina dati locali": "Cancella log, registri di esportazione e file temporanei salvati nella cartella dell'utente. Chiede conferma per dizionari e chiavi.",
    "Guida": "Apre la guida all'uso del programma (scorciatoia: F1).",
    "Info": "Versione del programma, controllo degli aggiornamenti e collegamento al repository.",
    "Esci": "Chiude il programma.",
    "NullifyPDF": "NullifyPDF: censura e pseudonimizzazione di PDF in locale.",
    "Privacy Edition": "Tutta l'elaborazione avviene sul tuo computer: nessun documento viene inviato in rete.",
    # Viewer toolbar
    "Visualizzatore Documento": "Anteprima del PDF. Trascina per segnare un'area da censurare; clicca su una censura per rimuoverla; Ctrl + rotella per lo zoom.",
    "-": "Riduce lo zoom.",
    "+": "Aumenta lo zoom.",
    "<": "Va alla pagina precedente.",
    ">": "Va alla pagina successiva.",
    "le_page": "Numero della pagina corrente. Scrivine un altro e premi Invio per saltarci.",
    "lbl_zoom": "Livello di zoom corrente.",
    "lbl_tot": "Numero totale di pagine del documento.",
    "view": "Anteprima del PDF. Trascina per segnare un'area da censurare; clicca su una censura o su un contorno arancione per decidere; Ctrl + rotella per lo zoom.",
    "prog": "Avanzamento dell'analisi, pagina per pagina.",
    "log": "Messaggi del programma: avanzamento, avvisi ed errori. Non contiene i dati personali trovati.",
    # Review dialog
    "Censura": "Applica la censura a questo elemento.",
    "Pag.": "Pagina in cui è stato trovato l'elemento.",
    "Valore": "Valore trovato, mascherato finché non spunti «Mostra i valori». Per le aree grafiche indica la zona.",
    "Tipo": "Tipo di dato rilevato (persona, luogo, telefono, firma...).",
    "Fonte": "Origine del suggerimento: regole, modello locale o OCR.",
    "Punteggio": "Affidabilità del rilevamento, da 0 a 1.",
    "Motivi": "Indizi che hanno portato a questo punteggio (contesto, parola comune, inizio riga...).",
    "Mostra i valori": "Mostra in chiaro i valori trovati nella tabella.",
    "Seleziona tutti": "Spunta tutti gli elementi dell'elenco.",
    "Nessuno": "Toglie la spunta a tutti gli elementi.",
    "Seleziona ≥ soglia": "Spunta gli elementi con punteggio pari o superiore alla soglia indicata a fianco.",
    "review_threshold": "Soglia di punteggio usata da «Seleziona ≥ soglia».",
    "Applica selezionati": "Censura gli elementi spuntati e scarta gli altri.",
    "Rivedi più tardi": "Chiude l'elenco lasciando i suggerimenti in sospeso.",
    "review_table": "Rilevamenti incerti: spunta quelli da censurare. Doppio clic su una riga per andare alla pagina.",
    # Dictionary dialog
    "dict_status": "Come sono protetti i dizionari su questo computer.",
    "Aggiungi": "Aggiunge un termine alla lista.",
    "Rimuovi": "Elimina i termini selezionati dalla lista.",
    "Importa da testo…": "Incolla più termini, uno per riga.",
    "Esporta in chiaro…": "Salva la lista in un file di testo non cifrato (contiene dati personali).",
    "Scadenza predefinita dei nuovi termini:": "Dopo quanto tempo i nuovi termini scadono e vengono eliminati da soli.",
    "dict_ttl": "Scadenza predefinita dei nuovi termini (anche quelli aggiunti dalla pagina).",
    "dict_tabs": "Blocklist: parole sempre censurate. Allowlist: parole mai censurate.",
    "dict_table": "Termini della lista con data di inserimento e scadenza (AAAA-MM-GG oppure Mai). Doppio clic per modificare.",
    "Salva": "Salva le modifiche ai dizionari.",
    # Entity dialog
    "Seleziona tutto": "Seleziona tutti i tipi di dato.",
    "Deseleziona tutto": "Deseleziona tutti i tipi di dato.",
    "Seleziona i dati da censurare / pseudonimizzare:": "Scegli quali tipi di dati cercare. La scelta viene ricordata.",
    # Guide
    "Chiudi": "Chiude questa finestra.",
    "OK": "Conferma la scelta e prosegue.",
    "Cancel": "Chiude senza confermare.",
    "Annulla": "Chiude senza confermare.",
    "Controlla aggiornamenti": "Cerca su GitHub se esiste una versione più recente del programma.",
    "Controlla ad ogni avvio": "Controlla gli aggiornamenti a ogni avvio. Disattivato di default; mostra qualcosa solo se c'è una versione nuova.",
    "Download": "Scarica nella cartella Download il file di installazione della nuova versione.",
}

# Visible text of the entity checkboxes -> tooltip.
ENTITY_TOOLTIPS: Dict[str, str] = {
    "Nomi e cognomi": "Persone citate nel testo. Le parole comuni e i titoli vengono scartati; i casi incerti vanno in revisione.",
    "Luoghi e indirizzi": "Città, indirizzi con numero civico e CAP (solo in un contesto di indirizzo).",
    "Email": "Indirizzi di posta elettronica.",
    "Telefono": "Numeri di telefono italiani e internazionali (date e numeri d'ordine sono esclusi).",
    "IBAN": "Coordinate bancarie IBAN valide.",
    "Carte di credito": "Numeri di carta di credito con controllo di validità.",
    "Wallet crypto": "Indirizzi di portafogli di criptovalute.",
    "Codice fiscale": "Codice fiscale italiano, con controllo del carattere finale.",
    "Partita IVA": "Partita IVA italiana, con controllo di validità e parola di contesto.",
    "Patente": "Numero di patente di guida (richiede la parola «patente» vicino).",
    "Carta d'identità": "Numero di carta d'identità (richiede il contesto).",
    "Passaporto": "Numero di passaporto (richiede il contesto).",
    "Date di nascita": "Date precedute da «nato/a il», «nascita»...",
    "Identificativi sanitari": "Numero della tessera sanitaria (20 cifre) e della ricetta elettronica (NRE).",
    "Codici di esenzione": "Codici di esenzione dal ticket (richiedono la parola «esenzione»).",
}


def tooltip_for(widget: QWidget) -> str:
    """Tooltip text for a widget, from its object name or visible text."""
    name = widget.objectName()
    if name and name in TOOLTIPS:
        return TOOLTIPS[name]
    text = ""
    if isinstance(widget, (QAbstractButton, QLabel)):
        text = widget.text() if hasattr(widget, "text") else ""
    text = re.sub(r"<[^>]+>", "", text).strip()
    if text in TOOLTIPS:
        return TOOLTIPS[text]
    if text in ENTITY_TOOLTIPS:
        return ENTITY_TOOLTIPS[text]
    if text.startswith("Rivedi suggerimenti"):
        return TOOLTIPS["Rivedi suggerimenti"]
    if text.startswith("Archivio protetto") or text.startswith("File chiave") or text == "Non cifrato" or text.startswith("Non ancora creato"):
        return TOOLTIPS["dict_status"]
    if text.endswith("%"):
        return TOOLTIPS["lbl_zoom"]
    if text.startswith("/ "):
        return TOOLTIPS["lbl_tot"]
    return _generic_tooltip(widget, text)


def _generic_tooltip(widget: QWidget, text: str) -> str:
    """Texts that vary at run time (Info and update dialogs)."""
    low = text.lower()
    if isinstance(widget, QLabel):
        if re.match(r"^v\d", low):
            return "Versione del programma installata."
        if "censura e pseudonimizzazione" in low:
            return "Informazioni sul programma, sull'autore e sulla licenza."
        if "github.com" in low or "repository" in low:
            return "Pagina del progetto su GitHub."
        if low.startswith("nuova versione"):
            return "Versione più recente disponibile."
        if low.startswith(("disponibile", "nessun aggiornamento", "controllo", "scaricato", "download")):
            return "Esito dell'operazione in corso."
        if low.startswith("questi elementi"):
            return "Spiega perché questi elementi sono suggerimenti e non censure automatiche."
        if low.startswith("http"):
            return "Collegamento alla pagina della release."
    return ""


# Widgets that deliberately have no tooltip: it would get in the way while reading.
NO_TOOLTIP = frozenset({"guide_topics", "guide_text"})

_INTERACTIVE: Tuple[type, ...] = (
    QAbstractButton, QLabel, QLineEdit, QProgressBar, QTextEdit, QGraphicsView,
    QTableWidget, QComboBox, QDoubleSpinBox, QTabWidget, QListWidget, QTextBrowser,
)


def apply_tooltips(root: QWidget) -> int:
    """Set a tooltip on every widget under `root` that has none. Returns the count."""
    n = 0
    for w in [root, *root.findChildren(QWidget)]:
        if not isinstance(w, _INTERACTIVE) or w.toolTip() or w.objectName() in NO_TOOLTIP:
            continue
        tip = tooltip_for(w)
        if tip:
            w.setToolTip(tip)
            n += 1
    return n


def widgets_without_tooltip(root: QWidget) -> List[str]:
    """Descriptions of interactive widgets that still have no tooltip."""
    missing: List[str] = []
    for w in root.findChildren(QWidget):
        if isinstance(w, _INTERACTIVE) and not w.toolTip() and w.objectName() not in NO_TOOLTIP:
            # Icons and the inner widgets of composite controls carry no text.
            if isinstance(w, QLabel) and not w.text().strip():
                continue
            if w.parent() is not None and type(w.parent()).__name__ in (
                "QAbstractSpinBox", "QTabBar", "QHeaderView", "QScrollBar",
                "QDoubleSpinBox", "QComboBox", "QTableWidget",
            ):
                continue
            if type(w).__name__ in ("QLineEdit",) and w.parent() is not None and isinstance(
                w.parent(), (QDoubleSpinBox, QComboBox)
            ):
                continue
            missing.append(f"{type(w).__name__}({getattr(w, 'text', lambda: '')()!r}, {w.objectName()!r})")
    return missing


# --------------------------------------------------------------------------
# Guide
# --------------------------------------------------------------------------

GUIDE_TOPICS: List[Tuple[str, str]] = [
    ("Introduzione", """
<h2>Introduzione</h2>
<p>NullifyPDF individua i dati personali in un PDF e li <b>censura</b> in modo irreversibile oppure li sostituisce con <b>segnaposto</b> reversibili (pseudonimizzazione). Tutta l'elaborazione avviene <b>sul tuo computer</b>: nessun documento viene inviato in rete.</p>
<p><b>Flusso consigliato</b></p>
<ol>
<li><b>Apri PDF</b> (o trascina il file sulla finestra).</li>
<li>Scegli la <b>lingua</b> del documento.</li>
<li>Premi <b>Auto Redact</b> e scegli i tipi di dati da cercare.</li>
<li>Rivedi i <b>suggerimenti</b> incerti e correggi a mano ciò che serve.</li>
<li>Premi <b>Esporta PDF</b>, scegli la modalità e controlla il risultato.</li>
</ol>
<p>Finché non esporti, le censure sono solo segni sull'anteprima: il documento originale non viene modificato.</p>
"""),
    ("Aprire un PDF e muoversi", """
<h2>Aprire un PDF e muoversi</h2>
<ul>
<li><b>Apri PDF</b> carica un file; si può anche trascinarlo sulla finestra. I PDF protetti da password non sono supportati.</li>
<li><b>&lt;</b> e <b>&gt;</b> cambiano pagina; nel campo numerico puoi scrivere una pagina e premere Invio.</li>
<li><b>+</b> e <b>-</b> cambiano lo zoom; anche <b>Ctrl + rotella</b> del mouse.</li>
<li>Se il PDF sembra una scansione (senza testo selezionabile) il programma lo segnala: attiva <b>OCR PDF scansionati</b> prima di analizzarlo.</li>
</ul>
"""),
    ("Lingua e opzioni", """
<h2>Lingua e opzioni</h2>
<p><b>Lingua</b>: il programma analizza documenti in italiano. Il modello italiano non è incluso nell'installer (licenza non commerciale): al primo utilizzo il programma mostra la licenza e chiede il consenso per scaricarlo.</p>
<ul>
<li><b>Oscura Immagini</b>: censura anche tutte le immagini (loghi, foto, firme) quando applichi Auto Redact.</li>
<li><b>OCR PDF scansionati</b>: legge con l'OCR le pagine scansionate e le immagini incorporate nelle pagine di testo. Richiede i dati di Tesseract (inclusi nei pacchetti).</li>
<li><b>Mostra suggerimenti</b>: contorna in arancione i suggerimenti da rivedere.</li>
<li><b>Profilo documenti sanitari</b>: vedi l'argomento dedicato.</li>
<li><b>Maschera larghezza testo rimosso</b>: arrotonda lo spazio lasciato dal testo cancellato, che altrimenti ne rivela la larghezza. Può spostare di poco il testo seguente; è disattivata di default.</li>
</ul>
"""),
    ("Modelli locali", """
<h2>Modelli locali</h2>
<p><b>Modelli locali</b> mostra il catalogo curato dei modelli candidati per migliorare i suggerimenti su nomi, indirizzi e altri dati personali. I modelli, quando abilitati, lavorano solo sul testo estratto e non applicano censure da soli.</p>
<ul>
<li>Ogni modello deve avere una licenza, una revisione e un <b>SHA-256</b> verificati.</li>
<li>Il programma non carica codice remoto, file pickle o modelli arbitrari.</li>
<li>Il download richiede consenso esplicito e i pesi vengono conservati nella cartella dell'utente, non nell'installer.</li>
<li>La qualità dei modelli va misurata sul tipo di documento concreto: nessun modello garantisce anonimizzazione o copertura completa.</li>
</ul>
"""),
    ("Auto Redact", """
<h2>Auto Redact</h2>
<p>Premendo <b>Auto Redact</b> scegli quali tipi di dati cercare (nomi, luoghi, email, telefono, IBAN, carte, codice fiscale, partita IVA, patente, carta d'identità, passaporto, e con il profilo sanitario date di nascita, tessera sanitaria, ricetta, esenzioni). La scelta viene ricordata.</p>
<p>Il programma assegna a ogni nome o luogo un <b>punteggio</b> basato su indizi nel testo: titoli e formule come «nato a» o «residente in», forma da nome proprio, nomi e luoghi noti, ripetizioni. Verbi e parole comuni di certificati e atti («Certifico», «Prescrivo», «Anamnesi»...) vengono scartati.</p>
<ul>
<li><b>Alto</b>: la censura viene segnata subito (riquadro nero).</li>
<li><b>Incerto</b>: diventa un <b>suggerimento</b> da rivedere. Non viene applicato né perso.</li>
<li><b>Molto basso</b>: scartato (nel profilo sanitario diventa comunque un suggerimento).</li>
</ul>
<p>I codici con controllo di validità (IBAN, carte, codice fiscale) vengono censurati interi anche se attaccati a un'etichetta.</p>
"""),
    ("Revisione dei suggerimenti", """
<h2>Revisione dei suggerimenti</h2>
<p>Al termine dell'analisi si apre l'elenco dei suggerimenti: pagina, valore (mascherato finché non spunti <i>Mostra i valori</i>), tipo, punteggio, fonte e motivi.</p>
<ul>
<li>Spunta gli elementi da censurare e premi <b>Applica selezionati</b>: gli altri vengono scartati.</li>
<li><b>Seleziona ≥ soglia</b> spunta in blocco gli elementi con punteggio alto.</li>
<li>Il campo <b>Tipo</b> è modificabile: controlla o correggi la categoria prima di applicare il suggerimento.</li>
<li>La colonna <b>Fonte</b> distingue regole, modello locale e OCR.</li>
<li><b>Rivedi più tardi</b> lascia tutto in sospeso; il pulsante <b>Rivedi suggerimenti (N)</b> nella barra laterale riapre l'elenco.</li>
<li>Doppio clic su una riga porta alla pagina; selezionando una riga il suo contorno si evidenzia.</li>
</ul>
<p>Sulla pagina i suggerimenti compaiono come contorni arancioni (solo a video): clicca su uno per scegliere <i>Censura</i>, <i>Scarta</i> o <i>Mostra valore</i>.</p>
<p>All'esportazione, se restano suggerimenti non revisionati, il programma te lo ricorda: non verranno censurati.</p>
"""),
    ("Correzioni manuali", """
<h2>Correzioni manuali</h2>
<ul>
<li><b>Aggiungere una censura</b>: trascina con il mouse un rettangolo sull'area da censurare. Se contiene testo puoi aggiungerlo alla blocklist, così sarà censurato in ogni documento futuro; se è un'area senza testo (immagine) viene oscurata come immagine.</li>
<li><b>Togliere una censura</b>: clicca sul riquadro. Puoi aggiungere quel testo all'allowlist per non vederlo più censurato.</li>
<li><b>Pulisci Pagina</b> toglie tutte le censure della pagina corrente.</li>
</ul>
"""),
    ("Dizionari", """
<h2>Dizionari</h2>
<p>I <b>Dizionari</b> contengono due liste: la <b>blocklist</b> (parole sempre censurate) e l'<b>allowlist</b> (parole mai censurate). Il confronto avviene per parola intera: una parola in allowlist non nasconde mai un valore diverso o più lungo.</p>
<ul>
<li>Ogni termine ha data di inserimento e <b>scadenza</b> (AAAA-MM-GG oppure <i>Mai</i>); i termini scaduti vengono eliminati da soli. <i>Scadenza predefinita</i> si applica ai nuovi termini, anche a quelli aggiunti dalla pagina.</li>
<li><b>Aggiungi</b>, <b>Rimuovi</b>, <b>Importa da testo…</b> (un termine per riga) e <b>Esporta in chiaro…</b> (il file contiene dati personali).</li>
<li>Le liste sono <b>cifrate</b> per l'utente corrente (Windows DPAPI, portachiavi di sistema se disponibile, altrimenti un file chiave locale con protezione limitata). Copiate su un altro account o PC non sono leggibili: il programma non le cancella e le mostra vuote.</li>
</ul>
"""),
    ("Esportare", """
<h2>Esportare</h2>
<p><b>Esporta PDF</b> crea il file finale. Si sceglie tra:</p>
<ul>
<li><b>Rimozione irreversibile</b>: i valori selezionati vengono eliminati dal file. Non si può tornare indietro dal file esportato.</li>
<li><b>Pseudonimizzazione reversibile</b>: i valori sono sostituiti da segnaposto e viene creata una <b>mappa di ripristino cifrata</b>, separata dal PDF.</li>
</ul>
<p><b>Stile dei segnaposto</b>: <i>Casuale</i> (consigliato, non rivela ordine né numero dei valori), <i>Progressivo</i> (PERSON_001... rivela quanti valori distinti ci sono), <i>Generico</i> (nasconde anche il tipo), <i>Coerente (chiave)</i> (lo stesso valore ha lo stesso segnaposto in tutti i documenti creati con la stessa chiave; collega i documenti tra loro). <i>Gestisci chiave...</i> esporta o importa la chiave protetta da password per usarla su un altro computer.</p>
<p><b>Mappa di ripristino</b>: salvala lontano dal PDF e non in una cartella sincronizzata. Servono una password (almeno 12 caratteri, chiesta due volte) e, volendo, una <b>chiave di recupero</b> mostrata una sola volta: conservala in un luogo sicuro, il programma non la salva.</p>
<p><b>Cosa fa il programma in esportazione</b></p>
<ul>
<li>Lavora su una copia in memoria: il documento aperto e il file originale non cambiano.</li>
<li>Rimuove annotazioni, allegati, link esterni, segnalibri, script, metadati, testo invisibile e fuori pagina.</li>
<li><b>Verifica</b> il file scritto: se un valore rimosso è ancora leggibile, o resta un glifo della parola, te lo dice e puoi eliminare il file.</li>
<li>Scrive un registro (solo conteggi e hash, nessun dato personale).</li>
</ul>
<p>Il nome file suggerito non contiene il nome del documento originale. Se scegli un nome che contiene un valore da rimuovere vieni avvisato.</p>
<p><b>Attenzione</b>: la censura non garantisce l'anonimato. Date, luoghi o altri dettagli rimasti possono ancora identificare una persona. Controlla sempre il risultato. Un PDF pseudonimizzato e la sua mappa restano dati personali.</p>
"""),
    ("Ricostruire un PDF", """
<h2>Ricostruire un PDF</h2>
<p><b>Ricostruisci PDF</b> rimette i valori originali in un PDF pseudonimizzato.</p>
<ol>
<li>Scegli il PDF pseudonimizzato e la sua mappa (<i>.nullifypdf-map</i>).</li>
<li>Inserisci la <b>password</b>, oppure spunta <i>Usa la chiave di recupero</i> e digita la chiave (NPDF-...).</li>
<li>Scegli dove salvare il file ricostruito.</li>
</ol>
<p>Il programma controlla che la mappa corrisponda al PDF e ti dice quanti valori sono stati davvero ripristinati. Il file ricostruito contiene di nuovo tutti i dati personali: trattalo di conseguenza.</p>
"""),
    ("Documenti sanitari", """
<h2>Documenti sanitari</h2>
<p>Con <b>Profilo documenti sanitari</b> il programma cerca anche:</p>
<ul>
<li><b>date di nascita</b> (precedute da «nato/a il», «nascita»...);</li>
<li><b>tessera sanitaria</b> (20 cifre, struttura pubblicata, il carattere di controllo non è verificato);</li>
<li><b>numero di ricetta (NRE)</b> e <b>codici di esenzione</b>, che richiedono la loro etichetta nelle vicinanze;</li>
<li><b>CAP e numeri civici</b> in un contesto di indirizzo;</li>
<li><b>firme e timbri</b> vicini a «firma», «timbro», «il medico»...: sono sempre solo suggerimenti.</li>
</ul>
<p>In questa modalità nessun caso incerto viene scartato in silenzio: diventa un suggerimento da rivedere. I dati sanitari sono dati di categoria particolare (art. 9 GDPR): controlla sempre il risultato.</p>
"""),
    ("Dati locali e privacy", """
<h2>Dati locali e privacy</h2>
<p>Il programma conserva nella cartella dell'utente (<code>~/.nullifypdf</code>): dizionari cifrati, chiave dei segnaposto cifrata, registro rotante dei messaggi, registri di esportazione (solo conteggi e hash) e, per file molto grandi, una cartella temporanea privata svuotata dopo l'esportazione.</p>
<p><b>Elimina dati locali</b> cancella log, registri e file temporanei. Se confermi, elimina anche i dizionari e, con una seconda conferma, le chiavi: senza chiavi dizionari cifrati e chiave dei segnaposto diventano illeggibili.</p>
<p>Nessun valore rilevato viene scritto nei log. Nessun documento lascia il computer.</p>
"""),
    ("Info e aggiornamenti", """
<h2>Info e aggiornamenti</h2>
<p>La finestra <b>Info</b> mostra la versione e il collegamento al repository. Elenca anche la licenza del programma (AGPL-3.0-or-later) e quella di ogni componente e modello usato, con i collegamenti ai testi ufficiali. <b>Controlla aggiornamenti</b> interroga le release pubblicate su GitHub; con <i>Controlla ad ogni avvio</i> (disattivato di default) il controllo è eseguito all'avvio e mostra qualcosa solo se esiste una versione più recente.</p>
"""),
    ("Scorciatoie", """
<h2>Scorciatoie</h2>
<table border="0" cellpadding="4">
<tr><td><b>F1</b> o il pulsante <b>Guida</b></td><td>Apre questa guida</td></tr>
<tr><td><b>Ctrl + rotella</b></td><td>Zoom dell'anteprima</td></tr>
<tr><td><b>Trascina</b> sull'anteprima</td><td>Segna un'area da censurare</td></tr>
<tr><td><b>Clic</b> su una censura</td><td>La rimuove</td></tr>
<tr><td><b>Clic</b> su un contorno arancione</td><td>Decide un suggerimento</td></tr>
<tr><td><b>Trascina un PDF</b> sulla finestra</td><td>Lo apre</td></tr>
</table>
<p>Passando il mouse su un elemento dell'interfaccia per qualche secondo compare una breve descrizione.</p>
"""),
    ("Limiti e problemi comuni", """
<h2>Limiti e problemi comuni</h2>
<ul>
<li>Il riconoscimento è statistico: controlla sempre il risultato prima di condividere un file. Nomi e luoghi non rilevati o dati indiretti restano.</li>
<li>Con righe molto ravvicinate (circa metà del corpo del carattere o meno) non esiste un riquadro che risparmi le righe vicine: compare un avviso e parole adiacenti possono essere danneggiate, mai lasciate leggibili.</li>
<li>Il testo dentro un'immagine viene rimosso solo dove l'immagine è censurata; per trovarlo serve l'OCR.</li>
<li>Se una parola comune viene proposta, scartala in revisione o aggiungila all'allowlist.</li>
<li>Se i dizionari risultano vuoti dopo aver copiato il profilo su un altro PC, vedi l'argomento Dizionari.</li>
<li>Le mappe create da questa versione non si aprono con versioni precedenti.</li>
</ul>
"""),
]


class GuideDialog(QDialog):
    """Topic list on the left, text on the right. Opened with F1."""

    def __init__(self, parent: Any = None, topic: int = 0) -> None:
        super().__init__(parent)
        self.setWindowTitle("Guida - NullifyPDF")
        self.resize(900, 620)
        lay = QHBoxLayout(self)
        self.topics = QListWidget()
        self.topics.setObjectName("guide_topics")
        self.topics.setFixedWidth(230)
        for title, _html in GUIDE_TOPICS:
            self.topics.addItem(title)
        left = QVBoxLayout()
        left.addWidget(self.topics)
        btn = QPushButton("Chiudi")
        btn.clicked.connect(self.accept)
        left.addWidget(btn)
        lay.addLayout(left)
        self.text = QTextBrowser()
        self.text.setObjectName("guide_text")
        self.text.setOpenExternalLinks(True)
        lay.addWidget(self.text, 1)
        self.topics.currentRowChanged.connect(self._show)
        self.topics.setCurrentRow(max(0, min(topic, len(GUIDE_TOPICS) - 1)))
        apply_tooltips(self)  # skips the topic list and the text: no hover popups while reading

    def _show(self, row: int) -> None:
        if 0 <= row < len(GUIDE_TOPICS):
            self.text.setHtml(GUIDE_TOPICS[row][1])
            self.text.moveCursor(self.text.textCursor().MoveOperation.Start)


__all__ = [
    "GUIDE_TOPICS", "GuideDialog", "TOOLTIPS", "ENTITY_TOOLTIPS",
    "apply_tooltips", "tooltip_for", "widgets_without_tooltip", "Qt",
]
