"""Small ONNX token-classification adapter without PyTorch."""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

from model_manager import ModelManifest, ModelManifestError, verify_model_files


@dataclass(frozen=True)
class ModelEntity:
    start: int
    end: int
    text: str
    label: str
    score: float


def _group_label(label: str) -> Optional[str]:
    label = label.upper().removeprefix("B-").removeprefix("I-")
    if label in {"PERSON", "PERSON_NAME", "FULLNAME", "FIRSTNAME", "LASTNAME", "MIDDLENAME"}:
        return "PERSON"
    if label in {"ORGANIZATION", "ORG"}:
        return "LOCATION"
    if label in {"ADDRESS", "STREET_ADDRESS", "CITY", "POSTAL_CODE"}:
        return "LOCATION"
    if label == "EMAIL_ADDRESS":
        return "EMAIL_ADDRESS"
    if label == "EMAIL":
        return "EMAIL_ADDRESS"
    if label == "PHONE_NUMBER":
        return "PHONE_NUMBER"
    if label == "PHONE":
        return "PHONE_NUMBER"
    if label == "PAYMENT_CARD_NUMBER":
        return "CREDIT_CARD"
    if label == "CREDITCARD":
        return "CREDIT_CARD"
    if label == "DRIVER_LICENSE_NUMBER":
        return "IT_DRIVER_LICENSE"
    if label == "PASSPORT_NUMBER":
        return "IT_PASSPORT"
    if label == "TAX_ID":
        return "IT_FISCAL_CODE"
    if label == "IBAN":
        return "IBAN_CODE"
    if label in {"DATEOFBIRTH", "DATE_OF_BIRTH"}:
        return "DATE_OF_BIRTH"
    if label in {"GOVERNMENT_ID", "ID_DOC"}:
        return "IT_IDENTITY_CARD"
    return None


class OnnxTokenDetector:
    """Run a verified token classifier and return source-text entities."""

    def __init__(self, model_dir: pathlib.Path, manifest: ModelManifest) -> None:
        verify_model_files(model_dir, manifest)
        try:
            import onnxruntime as ort  # type: ignore[import-untyped]
            from tokenizers import Tokenizer
        except ImportError as exc:
            raise RuntimeError("servono onnxruntime e tokenizers per il modello locale") from exc
        self.manifest = manifest
        self._ort = ort
        config = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
        self._tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        max_length = min(int(config.get("max_position_embeddings", 256)), 512)
        pad_id = int(config.get("pad_token_id", 0))
        self._tokenizer.enable_truncation(max_length=max_length)
        self._tokenizer.enable_padding(length=max_length, pad_id=pad_id, pad_token="<pad>")
        onnx_name = next(f.name for f in manifest.files if f.name.endswith(".onnx"))
        self._session = ort.InferenceSession(
            str(model_dir / onnx_name), providers=["CPUExecutionProvider"]
        )
        self._labels = {int(k): str(v) for k, v in config.get("id2label", {}).items()}
        if not self._labels:
            self._labels = {i: label for i, label in enumerate(manifest.labels)}

    def detect(self, text: str) -> List[ModelEntity]:
        if not text.strip():
            return []
        encoding = self._tokenizer.encode(text)
        ids = np.asarray([encoding.ids], dtype=np.int64)
        attention = np.asarray([encoding.attention_mask], dtype=np.int64)
        feeds: Dict[str, Any] = {}
        for input_meta in self._session.get_inputs():
            name = input_meta.name
            if name == "input_ids":
                feeds[name] = ids
            elif name == "attention_mask":
                feeds[name] = attention
            elif name == "token_type_ids":
                feeds[name] = np.zeros_like(ids)
        if "input_ids" not in feeds or "attention_mask" not in feeds:
            raise RuntimeError("input ONNX non compatibili con token-classification")
        output = self._session.run(None, feeds)[0]
        logits = np.asarray(output)[0]
        entities: List[ModelEntity] = []
        current: Optional[Tuple[int, int, str, float]] = None
        current_label = ""
        offsets = encoding.offsets
        for index, row in enumerate(logits):
            label = self._labels.get(int(np.argmax(row)), "O")
            score = float(np.exp(row - np.max(row))[int(np.argmax(row))] / np.exp(row - np.max(row)).sum())
            if index >= len(offsets) or offsets[index][0] == offsets[index][1]:
                continue
            start, end = offsets[index]
            if label == "O":
                if current is not None:
                    entities.append(ModelEntity(current[0], current[1], current[2], current_label, current[3]))
                    current = None
                continue
            prefix, _, raw_label = label.partition("-")
            group = _group_label(raw_label)
            if group is None:
                continue
            if current is None or prefix == "B" or current_label != group or start > current[1]:
                if current is not None:
                    entities.append(ModelEntity(current[0], current[1], current[2], current_label, current[3]))
                current = (start, end, text[start:end], score)
                current_label = group
            else:
                current = (current[0], end, text[current[0]:end], min(current[3], score))
        if current is not None:
            entities.append(ModelEntity(current[0], current[1], current[2], current_label, current[3]))
        return [e for e in entities if e.text.strip() and 0 <= e.start < e.end <= len(text)]


__all__ = ["ModelEntity", "OnnxTokenDetector"]
