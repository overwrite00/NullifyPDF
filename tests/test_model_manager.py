from pathlib import Path

import pytest

from model_manager import (
    HardwareProfile,
    ModelFile,
    ModelManifest,
    ModelManifestError,
    ModelStore,
    recommend_level,
    verify_model_files,
)


def _manifest(data: bytes = b"model") -> ModelManifest:
    import hashlib

    return ModelManifest(
        model_id="test-model",
        repo_id="example/model",
        revision="0123456789abcdef0123456789abcdef01234567",
        license="MIT",
        runtime="onnx",
        labels=("PERSON",),
        files=(ModelFile("model.onnx", len(data), hashlib.sha256(data).hexdigest()),),
        enabled=True,
    )


def test_manifest_rejects_short_revision_and_unsafe_file():
    m = _manifest()
    with pytest.raises(ModelManifestError):
        ModelManifest(**{**m.__dict__, "revision": "abc"}).validate()
    with pytest.raises(ModelManifestError):
        ModelFile("../model.onnx", 1, "0" * 64).validate()


def test_verify_model_files_checks_size_and_hash(tmp_path: Path):
    m = _manifest()
    model_dir = tmp_path / m.model_id / m.revision
    model_dir.mkdir(parents=True)
    (model_dir / "model.onnx").write_bytes(b"model")
    verify_model_files(model_dir, m)
    (model_dir / "model.onnx").write_bytes(b"tampered")
    with pytest.raises(ModelManifestError, match="dimensione inattesa|hash"):
        verify_model_files(model_dir, m)


def test_store_is_installed_requires_complete_verified_files(tmp_path: Path):
    m = _manifest()
    store = ModelStore(tmp_path)
    assert not store.is_installed(m)
    target = store.model_dir(m)
    target.mkdir(parents=True)
    (target / "model.onnx").write_bytes(b"model")
    assert store.is_installed(m)


def test_recommendation_does_not_enable_unverified_catalog():
    hw = HardwareProfile(cpu_count=12, memory_bytes=16 * 1024**3)
    assert recommend_level(hw, ()).level == "nessuno"
    low = HardwareProfile(cpu_count=12, memory_bytes=4 * 1024**3)
    assert recommend_level(low, (_manifest(),)).model_id is None


def test_manifest_rejects_non_model_extensions():
    with pytest.raises(ModelManifestError):
        ModelFile("training_args.bin", 1, "0" * 64).validate()


def test_manifest_source_url_is_pinned():
    manifest = _manifest()
    assert manifest.revision in manifest.source_url
    assert manifest.source_url.startswith("https://huggingface.co/")
