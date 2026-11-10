"""Local model catalog, integrity checks and user-managed downloads.

This module deliberately does not import an inference framework.  Model files
are untrusted data until their manifest, revision, size and SHA-256 digest have
been checked.  Loading an ONNX graph belongs to a separate runtime adapter.
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import platform
import re
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional, Tuple


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REVISION = re.compile(r"^[0-9a-f]{40}$")
_SAFE_SUFFIXES = frozenset({".onnx", ".ort", ".data", ".json", ".safetensors"})
_MAX_MANIFEST_FILES = 32


class ModelManifestError(ValueError):
    """Raised when a model manifest is malformed or unsafe."""


@dataclass(frozen=True)
class ModelFile:
    name: str
    size: int
    sha256: str

    def validate(self) -> None:
        path = pathlib.PurePosixPath(self.name)
        if not self.name or path.is_absolute() or ".." in path.parts:
            raise ModelManifestError("percorso file modello non sicuro")
        if path.suffix.lower() not in _SAFE_SUFFIXES:
            raise ModelManifestError(f"formato modello non consentito: {self.name}")
        if self.size <= 0:
            raise ModelManifestError("dimensione file non valida")
        if not _SHA256.fullmatch(self.sha256):
            raise ModelManifestError("SHA-256 non valido")


@dataclass(frozen=True)
class ModelManifest:
    model_id: str
    repo_id: str
    revision: str
    license: str
    runtime: str
    labels: Tuple[str, ...]
    files: Tuple[ModelFile, ...]
    enabled: bool = False
    notes: str = ""

    def validate(self) -> None:
        if not self.model_id or not self.repo_id:
            raise ModelManifestError("identificativo modello mancante")
        if not _REVISION.fullmatch(self.revision):
            raise ModelManifestError("la revisione deve essere un commit SHA-1 completo")
        if self.runtime not in {"onnx", "ort"}:
            raise ModelManifestError("runtime non consentito")
        if not self.license.strip():
            raise ModelManifestError("licenza mancante")
        if not self.files or len(self.files) > _MAX_MANIFEST_FILES:
            raise ModelManifestError("elenco file modello non valido")
        names = set()
        for item in self.files:
            item.validate()
            if item.name in names:
                raise ModelManifestError("file duplicato nel manifest")
            names.add(item.name)
        if self.runtime == "onnx" and not any(
            f.name.lower().endswith(".onnx") for f in self.files
        ):
            raise ModelManifestError("manifest ONNX senza file .onnx")

    @property
    def total_size(self) -> int:
        return sum(item.size for item in self.files)

    @property
    def source_url(self) -> str:
        return f"https://huggingface.co/{self.repo_id}/tree/{self.revision}"


@dataclass(frozen=True)
class HardwareProfile:
    cpu_count: int
    memory_bytes: Optional[int]
    system: str = platform.system()


@dataclass(frozen=True)
class ModelRecommendation:
    level: str
    model_id: Optional[str]
    reason: str


@dataclass(frozen=True)
class ModelCandidate:
    """Reviewed catalog entry which is not necessarily installable yet."""

    model_id: str
    title: str
    repo_id: str
    license: str
    runtime: str
    languages: Tuple[str, ...]
    size_label: str
    scope: str
    status: str
    notes: str


MODEL_CANDIDATES: Tuple[ModelCandidate, ...] = (
    ModelCandidate(
        "minilmv2-en-it",
        "MiniLMv2 EN/IT",
        "jkomyno/minilmv2-l6-h384-ner-en-it-q8",
        "MIT",
        "ONNX INT8",
        ("en", "it"),
        "circa 30 MB",
        "persone, organizzazioni, indirizzi",
        "verificato",
        "Candidato leggero; non copre gli identificativi strutturati.",
    ),
    ModelCandidate(
        "piiscan",
        "PiiScan",
        "vectorsense/piiscan",
        "Apache-2.0",
        "ONNX INT8",
        ("multilingue",),
        "circa 139 MB",
        "PII generiche e identificativi",
        "manifest verificato; italiano da misurare",
        "La scheda dichiara 30 lingue, ma non elenca esplicitamente l'italiano.",
    ),
    ModelCandidate(
        "openmed-fastclinical",
        "OpenMed PII Italian FastClinical Small",
        "OpenMed/OpenMed-PII-Italian-FastClinical-Small-82M-v1-onnx-android",
        "Apache-2.0",
        "ONNX INT8",
        ("it",),
        "circa 190 MB",
        "PII e identificativi clinici italiani",
        "verificato",
        "Modello italiano specializzato in testo clinico; esempi dichiarati sintetici.",
    ),
    ModelCandidate(
        "nym-pii",
        "nym PII multilingual",
        "Wismut/nym-pii-multilingual",
        "MIT",
        "ONNX INT8",
        ("multilingue",),
        "circa 359 MB INT8",
        "PII, OCR rumoroso, documenti strutturati",
        "sperimentale",
        "Maggiore costo di memoria; qualità italiana da misurare.",
    ),
    ModelCandidate(
        "eu-pii-safeguard",
        "EU PII Safeguard",
        "tabularisai/eu-pii-safeguard",
        "da verificare",
        "ONNX derivato",
        ("26 lingue UE",),
        "non verificata",
        "PII europee",
        "sperimentale",
        "La conversione ONNX e la licenza del sorgente richiedono verifica.",
    ),
)


MINILM_REVISION = "61dd72a5cac8e8d3e2702b57cba8154a8720c2af"
PIISCAN_REVISION = "87e6ff6245ea325880af9f38e6dad8493f2ec123"


VERIFIED_MANIFESTS: Tuple[ModelManifest, ...] = (
    ModelManifest(
        model_id="minilmv2-en-it",
        repo_id="jkomyno/minilmv2-l6-h384-ner-en-it-q8",
        revision=MINILM_REVISION,
        license="MIT",
        runtime="onnx",
        labels=("O", "B-ADDRESS", "I-ADDRESS", "B-ORGANIZATION", "I-ORGANIZATION", "B-PERSON", "I-PERSON"),
        files=(
            ModelFile("config.json", 1075, "8f4608824f674a3a2427fc6751ebf3cc64766f3c14e3976cb0c46fbbb4dbc83b"),
            ModelFile("tokenizer.json", 3558647, "7b62d797c95d1563d3467f48daad0eca3e150f2d587e7e687b557c9ef1b25473"),
            ModelFile("tokenizer_config.json", 387, "e8ba8e4ec2ade6868d62c5d8a993c49cd44cdcf34aadc58bd764b5f4e752e338"),
            ModelFile("onnx/model_quantized.onnx", 30585613, "d1fb8efd376b7026faeba43aa60b602d28902d3a99ca9bfa19bce1edcbded5a8"),
        ),
        enabled=True,
        notes="Modello leggero per PERSON, ORGANIZATION e ADDRESS.",
    ),
    ModelManifest(
        model_id="piiscan",
        repo_id="vectorsense/piiscan",
        revision=PIISCAN_REVISION,
        license="Apache-2.0",
        runtime="onnx",
        labels=("O", "B-PERSON_NAME", "I-PERSON_NAME", "B-DATE_TIME", "I-DATE_TIME", "B-EMAIL_ADDRESS", "I-EMAIL_ADDRESS", "B-CITY", "I-CITY", "B-STREET_ADDRESS", "I-STREET_ADDRESS", "B-GOVERNMENT_ID", "I-GOVERNMENT_ID", "B-PHONE_NUMBER", "I-PHONE_NUMBER", "B-AGE", "I-AGE", "B-POSTAL_CODE", "I-POSTAL_CODE", "B-PAYMENT_CARD_NUMBER", "I-PAYMENT_CARD_NUMBER", "B-DRIVER_LICENSE_NUMBER", "I-DRIVER_LICENSE_NUMBER", "B-TAX_ID", "I-TAX_ID", "B-PASSPORT_NUMBER", "I-PASSPORT_NUMBER"),
        files=(
            ModelFile("config.json", 2049, "42cafc5b1ebcaafd3fa99a261f042bffc627c7f9433f2ee70421e2f9cff85f56"),
            ModelFile("labels.json", 547, "d162bf06f29a8e5f09e7158c5847a531f0637e74b4b615286ff5fe931d6f7104"),
            ModelFile("thresholds.json", 1258, "098fddcfa67451a0b3e4243018f6cb540660ebc5abe28888e0ddd75269e6d6e2"),
            ModelFile("tokenizer.json", 2919461, "2c550ee6d187a1eeb0982a7af79b42748d7815c08b7221d01a8b06c4802316c3"),
            ModelFile("tokenizer_config.json", 1397, "d22f2844d37c4f6e15b7f5220c4e33597f328ff7461f585e759f7f9914d0a742"),
            ModelFile("model.int8.onnx", 135144362, "3ddde8cf53d34c4a6fc4c29ea2c1a28b65efdb84761e945b9afb45984a9c5342"),
        ),
        enabled=True,
        notes="Modello CPU multilanguage con offset esatti; italiano da misurare sul corpus dell'app.",
    ),
    ModelManifest(
        model_id="openmed-fastclinical",
        repo_id="OpenMed/OpenMed-PII-Italian-FastClinical-Small-82M-v1-onnx-android",
        revision="05cef784e0234e82c5806d2ec2451a1385c1d962",
        license="Apache-2.0",
        runtime="onnx",
        labels=("O", "B-FIRSTNAME", "B-LASTNAME", "B-CITY", "B-ORGANIZATION", "B-EMAIL", "B-PHONE", "B-IBAN", "B-DATEOFBIRTH", "B-STREET", "B-ZIPCODE"),
        files=(
            ModelFile("config.json", 4505, "a91d68ba87154e94053ef61db86583c60703aeb3d4961058ae9886fc60487996"),
            ModelFile("id2label.json", 1656, "a855c964ef7763ec51b63aad7ec43e43ae5a89f1e5f221cd2852326107ad7d95"),
            ModelFile("tokenizer.json", 3558906, "ca4e5a9389c0dd76c509ba115a772da3a85c43aa10b9dfb966782907062de52b"),
            ModelFile("tokenizer_config.json", 536, "828fb35f1e12914318c360d7b04f4c3fc4b7a9912b81cdf9ea37fb7a7da7d173"),
            ModelFile("model_int8.onnx", 199020782, "c29ad148bb8bd33392a2dd94bb469108ca70ab2e4fe3cca374a879cfb942d62c"),
        ),
        enabled=True,
        notes="ONNX INT8 CPU, 82M parametri, contesto 512; copertura italiana clinica da validare sul corpus dell'app.",
    ),
)


CATALOG: Tuple[ModelManifest, ...] = VERIFIED_MANIFESTS


def _windows_memory_bytes() -> Optional[int]:
    if platform.system() != "Windows":
        return None
    try:
        import ctypes

        class Status(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("memory_load", ctypes.c_ulong),
                ("total", ctypes.c_ulonglong),
                ("available", ctypes.c_ulonglong),
                ("total_page", ctypes.c_ulonglong),
                ("available_page", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong),
                ("available_virtual", ctypes.c_ulonglong),
                ("available_extended", ctypes.c_ulonglong),
            ]

        status = Status()
        status.length = ctypes.sizeof(Status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.total)
    except (AttributeError, OSError, TypeError):
        pass
    return None


def detect_hardware() -> HardwareProfile:
    """Return conservative hardware information using only the standard library."""
    return HardwareProfile(
        cpu_count=max(1, int(os.cpu_count() or 1)),
        memory_bytes=_windows_memory_bytes(),
    )


def recommend_level(
    hardware: HardwareProfile,
    manifests: Iterable[ModelManifest] = CATALOG,
) -> ModelRecommendation:
    """Recommend a level without enabling an unverified model."""
    available = [m for m in manifests if m.enabled]
    if hardware.memory_bytes is not None and hardware.memory_bytes < 8 * 1024**3:
        return ModelRecommendation("nessuno", None, "RAM inferiore alla soglia consigliata")
    if not available:
        return ModelRecommendation(
            "nessuno", None, "nessun modello verificato disponibile nel catalogo"
        )
    small = min(available, key=lambda m: m.total_size)
    return ModelRecommendation(
        "piccolo", small.model_id, "primo modello verificato compatibile disponibile"
    )


def sha256_file(path: pathlib.Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_model_files(directory: pathlib.Path, manifest: ModelManifest) -> None:
    """Verify presence, exact size and digest of every manifest file."""
    manifest.validate()
    root = directory.resolve()
    for item in manifest.files:
        path = (root / pathlib.PurePosixPath(item.name)).resolve()
        if root != path and root not in path.parents:
            raise ModelManifestError("file modello fuori dalla directory")
        if not path.is_file():
            raise ModelManifestError(f"file modello mancante: {item.name}")
        if path.stat().st_size != item.size:
            raise ModelManifestError(f"dimensione inattesa: {item.name}")
        if sha256_file(path) != item.sha256:
            raise ModelManifestError(f"hash non corrispondente: {item.name}")


class ModelStore:
    """Store models outside the repository and install them atomically."""

    def __init__(self, root: pathlib.Path) -> None:
        self.root = root

    def model_dir(self, manifest: ModelManifest) -> pathlib.Path:
        manifest.validate()
        return self.root / manifest.model_id / manifest.revision

    def is_installed(self, manifest: ModelManifest) -> bool:
        try:
            verify_model_files(self.model_dir(manifest), manifest)
            return True
        except (OSError, ModelManifestError):
            return False

    def install_file(
        self,
        manifest: ModelManifest,
        item: ModelFile,
        url: str,
        *,
        timeout: float = 30.0,
        progress: Optional[Callable[[int, int], None]] = None,
    ) -> pathlib.Path:
        """Download one HTTPS file, verify it, then atomically install it."""
        manifest.validate()
        item.validate()
        if not url.lower().startswith("https://"):
            raise ModelManifestError("sono consentiti solo download HTTPS")
        destination = self.model_dir(manifest) / pathlib.PurePosixPath(item.name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=".model-", suffix=".part", dir=str(destination.parent)
        )
        os.close(fd)
        temporary = pathlib.Path(temp_name)
        try:
            request = urllib.request.Request(url, headers={"Accept": "application/octet-stream"})
            with urllib.request.urlopen(request, timeout=timeout) as response, temporary.open("wb") as out:
                done = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    if progress is not None:
                        progress(done, item.size)
            if temporary.stat().st_size != item.size:
                raise ModelManifestError(f"dimensione inattesa: {item.name}")
            if sha256_file(temporary) != item.sha256:
                raise ModelManifestError(f"hash non corrispondente: {item.name}")
            os.replace(temporary, destination)
            return destination
        except (OSError, urllib.error.URLError, ModelManifestError):
            temporary.unlink(missing_ok=True)
            raise

