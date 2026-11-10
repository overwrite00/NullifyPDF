"""Italian lexicon used to tell ordinary words from names and places.

Qt-free. The NER model tags capitalised ordinary words (first-person verbs of
certificates and prescriptions, headings of medical or legal documents) as
PERSON or LOCATION. The lists below are used to *reject* such hits, or - for
the name and place lists - only to *confirm* a hit. A word missing from a
confirmation list never rejects a hit: no complete list of surnames exists.
"""

import functools
from typing import Any, FrozenSet, Iterable, Set

# Verb lemmas that occur as the first word of a line or clause in medical,
# legal and administrative documents.
_ARE = (
    "certific", "dichiar", "attest", "rilasci", "conferm", "raccomand",
    "consigli", "autorizz", "deleg", "nomin", "ordin", "dimett", "visit",
    "controll", "esamin", "accert", "constat", "verific", "comunic", "inform",
    "trasmett", "allegh", "firm", "sottoscriv", "richiam", "dispon", "invit",
    "diagnostic", "refert", "annot", "segnal", "propon", "suggerisc", "delegh",
    "notific", "attribu", "applic", "approv", "dichiaram", "liquid", "convoc",
)
_ERE = (
    "prescriv", "richied", "chied", "decid", "rilev", "present", "conced",
    "ritien", "consider", "ammett", "dispon", "stabil", "assum", "emett",
    "rispond", "compil", "ricev",
)
_IRE = (
    "convoc", "costitu", "attribu", "esegu", "adempi", "sostitu", "dimin",
    "prefer", "sped", "segu", "fornisc", "garantisc", "dispon", "consent",
    "ordin",
)

# (suffix set, participle suffixes)
_ARE_SUFFIXES = ("o", "i", "a", "iamo", "ate", "ano", "ato", "ata", "ati", "ate")
_ERE_SUFFIXES = ("o", "i", "e", "iamo", "ete", "ono", "uto", "uta", "uti", "ute")
_IRE_SUFFIXES = ("o", "i", "e", "iamo", "ite", "ono", "isco", "isci", "isce",
                 "iscono", "ito", "ita", "iti", "ite")


def _conjugate() -> Set[str]:
    out: Set[str] = set()
    for stem in _ARE:
        out.update(stem + s for s in _ARE_SUFFIXES)
    for stem in _ERE:
        out.update(stem + s for s in _ERE_SUFFIXES)
    for stem in _IRE:
        out.update(stem + s for s in _IRE_SUFFIXES)
    return out


_VERB_FORMS: FrozenSet[str] = frozenset(_conjugate() | {
    "visto", "considerato", "ritenuto", "premesso", "sottoscritto",
    "sottoscritta", "firmato", "firmata", "letto", "udito", "accertato",
    "ordina", "dispone", "dispongo", "decreta", "decreto", "sentenzia",
    "attesto", "prescrivo", "certifico", "dichiaro", "rilascio", "confermo",
    "raccomando", "consiglio", "richiedo", "autorizzo", "delego", "nomino",
})

_MEDICAL_LEGAL: FrozenSet[str] = frozenset({
    "anamnesi", "diagnosi", "terapia", "prognosi", "referto", "esame",
    "esami", "obiettivo", "paziente", "pazienti", "assistito", "assistita",
    "certificato", "ricetta", "posologia", "controllo", "visita", "allegato",
    "allegati", "timbro", "firma", "firme", "farmaco", "farmaci", "dose",
    "dosi", "sintomi", "sintomo", "referti", "cartella", "clinica", "clinico",
    "ricovero", "dimissione", "dimissioni", "ospedale", "reparto", "medico",
    "medici", "infermiere", "infermiera", "pronto", "soccorso", "idoneo",
    "idonea", "idoneità", "malattia", "infortunio", "prescrizione",
    "prestazione", "prestazioni", "ambulatorio", "analisi", "ematochimici",
    "ematochimico", "esito", "esiti", "conclusioni", "conclusione", "note",
    "nota", "motivazione", "motivazioni", "premesso", "considerato", "ritenuto",
    "decreto", "sentenza", "ordinanza", "ricorso", "ricorrente", "resistente",
    "convenuto", "attore", "giudice", "tribunale", "udienza", "istanza",
    "dispositivo", "pubblico", "ministero", "cancelleria", "notifica",
    "oggetto", "premessa", "articolo", "comma", "regolamento", "legge",
    "parti", "parte", "comparizione", "sottoscritto", "sottoscritta",
    "luogo", "data", "tel", "email", "pec", "totale", "importo", "imponibile",
    "fattura", "ricevuta", "scadenza", "pagamento", "saldo", "acconto",
    "raccomando", "riposo", "assoluto", "giorni", "giorno", "mesi", "anni",
    "tachipirina", "augmentin",
})

# Capitalised document words that are not personal data.
_DOCUMENT_WORDS: FrozenSet[str] = frozenset({
    "comune", "provincia", "regione", "ministero", "agenzia", "entrate",
    "università", "universita", "azienda", "ospedaliera", "sanitaria", "asl",
    "ausl", "spett", "srl", "spa", "snc", "sas", "onlus", "repubblica",
    "italiana", "stato", "governo", "inps", "inail", "ente", "ufficio",
    "uffici", "dipartimento", "direzione", "servizio", "sezione", "area",
    "settore", "segreteria", "protocollo", "pagina", "allegato", "copia",
    "originale", "documento", "modulo", "richiesta", "domanda", "dichiarazione",
    "autocertificazione", "informativa", "consenso", "privacy", "cordiali",
    "saluti", "distinti", "cordialmente", "grazie", "firma", "timbro",
})

# Words that are also given names or surnames: never rejected on lexicon
# grounds alone, they need corroborating context.
CONFLICT_NAMES: FrozenSet[str] = frozenset({
    "rosa", "serena", "sole", "fiore", "marino", "bruno", "bianco", "speranza",
    "vittoria", "pace", "conte", "porto", "grazia", "gioia", "felice", "primo",
    "santo", "fabbri", "mancini", "leone", "gallo", "colombo", "greco",
    "romano", "ricci", "costa", "moro", "russo", "ferrari", "neri", "verdi",
    "rossi", "gialli", "bella", "forte", "lupo", "orso", "martino",
})

GIVEN_NAMES: FrozenSet[str] = frozenset({
    "mario", "luigi", "giuseppe", "giovanni", "antonio", "francesco",
    "alessandro", "andrea", "marco", "luca", "paolo", "stefano", "roberto",
    "davide", "matteo", "simone", "lorenzo", "giorgio", "franco", "claudio",
    "carlo", "angelo", "pietro", "salvatore", "vincenzo", "michele", "fabio",
    "massimo", "daniele", "riccardo", "federico", "gabriele", "enrico",
    "maria", "anna", "giulia", "francesca", "chiara", "sara", "laura",
    "elena", "valentina", "alessandra", "paola", "silvia", "federica",
    "martina", "elisa", "roberta", "monica", "claudia", "lucia", "cristina",
    "daniela", "stefania", "barbara", "giovanna", "angela", "rita", "teresa",
    "graziano", "graziella", "nicola", "domenico", "emanuele", "filippo",
    "giacomo", "tommaso", "samuele", "edoardo", "gianluca", "gianni",
    "rosa", "serena", "giorgia", "alice", "arianna", "beatrice", "irene",
    "marta", "veronica", "ilaria", "manuela", "patrizia", "carla", "marina",
})

REGIONS_PROVINCES: FrozenSet[str] = frozenset({
    "abruzzo", "basilicata", "calabria", "campania", "emilia-romagna",
    "friuli-venezia", "lazio", "liguria", "lombardia", "marche", "molise",
    "piemonte", "puglia", "sardegna", "sicilia", "toscana", "trentino",
    "umbria", "veneto", "valle d'aosta",
    "roma", "milano", "napoli", "torino", "palermo", "genova", "bologna",
    "firenze", "bari", "catania", "venezia", "verona", "messina", "padova",
    "trieste", "brescia", "parma", "taranto", "prato", "modena", "reggio",
    "perugia", "livorno", "ravenna", "cagliari", "foggia", "rimini",
    "salerno", "ferrara", "sassari", "latina", "monza", "siracusa",
    "pescara", "bergamo", "forlì", "trento", "vicenza", "terni", "bolzano",
    "novara", "piacenza", "ancona", "andria", "arezzo", "udine", "cesena",
    "lecce", "pesaro", "la spezia", "como", "pisa", "lucca", "cosenza",
    "caserta", "avellino", "benevento", "potenza", "matera", "campobasso",
    "catanzaro", "crotone", "agrigento", "trapani", "ragusa", "enna",
    "caltanissetta", "aosta", "cuneo", "asti", "alessandria", "biella",
    "varese", "lecco", "sondrio", "pavia", "cremona", "mantova", "lodi",
    "belluno", "treviso", "rovigo", "gorizia", "pordenone", "savona",
    "imperia", "massa", "carrara", "pistoia", "siena", "grosseto",
    "viterbo", "rieti", "frosinone", "l'aquila", "teramo", "chieti",
    "isernia", "brindisi", "barletta", "oristano", "nuoro",
    "italia", "francia", "germania", "spagna", "svizzera", "austria",
})

COMMON_WORDS: FrozenSet[str] = frozenset(
    _VERB_FORMS | _MEDICAL_LEGAL | _DOCUMENT_WORDS
)

# Italian function words (articles, prepositions, conjunctions, pronouns) that
# may begin a capitalised sentence start.
FUNCTION_WORDS: FrozenSet[str] = frozenset({
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una", "di", "a", "da",
    "in", "con", "su", "per", "tra", "fra", "e", "ed", "o", "ma", "se", "che",
    "chi", "non", "più", "come", "quando", "dove", "anche", "ogni", "questo",
    "questa", "questi", "queste", "quello", "quella", "del", "della", "dei",
    "delle", "dello", "al", "alla", "ai", "alle", "allo", "nel", "nella",
    "nei", "nelle", "sul", "sulla", "sui", "sulle", "dal", "dalla", "dai",
    "dalle", "io", "tu", "lui", "lei", "noi", "voi", "loro", "mi", "ti", "si",
    "ci", "vi", "ne", "ho", "ha", "hanno", "è", "sono", "era", "sarà", "poi",
    "dopo", "prima", "oggi", "ieri", "domani", "tutti", "tutto", "nessun",
    "stesso", "stessa", "presso", "sotto", "sopra", "senza", "secondo",
    "nato", "nata", "residente", "domiciliato", "domiciliata",
})


# Italian vehicle-plate style province codes (107 provinces / metropolitan cities).
PROVINCE_SIGLE: FrozenSet[str] = frozenset(
    "AG AL AN AO AP AQ AR AT AV BA BG BI BL BN BO BR BS BT BZ CA CB CE CH CL CN "
    "CO CR CS CT CZ EN FC FE FG FI FM FR GE GO GR IM IS KR LC LE LI LO LT LU MB "
    "MC ME MI MN MO MS MT NA NO NU OR PA PC PD PE PG PI PN PO PR PT PU PV PZ RA "
    "RC RE RG RI RM RN RO SA SI SO SP SR SS SU SV TA TE TN TO TP TR TS TV UD VA "
    "VB VC VE VI VR VT VV".split()
)


def is_common_word(token: str) -> bool:
    """True for ordinary Italian words that are never PII on their own."""
    t = token.strip().lower().strip(".,;:!?()[]\"'«»")
    if not t:
        return True
    if t in CONFLICT_NAMES:
        return False
    return t in COMMON_WORDS or t in FUNCTION_WORDS


# Frequent Italian surnames (a small curated list: confirmation only).
SURNAMES: FrozenSet[str] = frozenset(
    "rossi russo ferrari esposito bianchi romano colombo ricci marino greco bruno "
    "gallo conti de luca mancini costa giordano rizzo lombardi moretti barbieri "
    "fontana santoro mariani rinaldi caruso ferrara galli martini leone longo "
    "gentile martinelli vitale lombardo serra coppola de santis d'angelo marchetti "
    "parisi villa conte ferraro ferri fabbri bianco marini grasso valentini messina "
    "sala de angelis gatti pellegrini palumbo sanna farina rizzi monti cattaneo "
    "morelli amato silvestri mazza testa grassi pellegrino carbone giuliani benedetti "
    "barone rossetti caputo montanari guerra palmieri bernardi martino fiore de rosa "
    "ferretti bellini basile riva donati piras vitali battaglia sartori neri costantini "
    "milani pagano ruggiero sorrentino d'amico orlando damico negri verdi gialli "
    "melis cocco leoni pace marchi mele".split()
)


def is_known_surname(token: str) -> bool:
    key = token.strip().lower().strip(".,;:")
    if key in SURNAMES:
        return True
    d = _data()
    return bool(d and hasattr(d, "NAMES_SURNAMES") and key in d.NAMES_SURNAMES
                and key not in d.NAMES_AMBIGUOUS)


def is_given_name(token: str) -> bool:
    key = token.strip().lower().strip(".,;:")
    if key in GIVEN_NAMES:
        return True
    d = _data()
    return bool(d and hasattr(d, "NAMES_GIVEN") and key in d.NAMES_GIVEN
                and key not in d.NAMES_AMBIGUOUS)


@functools.lru_cache(maxsize=1)
def _data() -> Any:
    """ISTAT-derived place data, imported on first use (not at start-up)."""
    try:
        import lexicon_data_it

        return lexicon_data_it
    except Exception:
        return None


def _place_key(token: str) -> str:
    return token.strip().lower().replace("’", "'").strip(".,;:()")


def is_known_place(token: str) -> bool:
    """A comune, region or country - confirmation only, never a rejection.

    Names that are also ordinary words (Sale, Re, Orso...) are *not* counted
    here; see :func:`is_ambiguous_place`.
    """
    key = _place_key(token)
    if key in REGIONS_PROVINCES:
        return True
    d = _data()
    return bool(d and (key in d.COMUNI or key in d.REGIONS) and key not in d.COMUNI_AMBIGUOUS)


def is_ambiguous_place(token: str) -> bool:
    """A comune whose name is also an ordinary word or a very short name."""
    key = _place_key(token)
    d = _data()
    return bool(d and key in d.COMUNI and key in d.COMUNI_AMBIGUOUS
                and key not in REGIONS_PROVINCES)


def province_codes() -> FrozenSet[str]:
    d = _data()
    return frozenset(PROVINCE_SIGLE | (d.PROVINCE_SIGLE if d else frozenset()))


def verb_forms() -> FrozenSet[str]:
    return _VERB_FORMS


def extend(words: Iterable[str]) -> FrozenSet[str]:
    """Return COMMON_WORDS extended with caller-supplied words."""
    return frozenset(COMMON_WORDS | {w.lower() for w in words})
