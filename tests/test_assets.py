"""Asset Pack v1、本地 Provider 与 WebGAL Adapter 的离线测试。"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest

from repo2gal.asset_pack import MAX_MANIFEST_BYTES, init_asset_pack, load_asset_pack
from repo2gal.errors import AssetPackError, PackageError
from repo2gal.packager import package
from repo2gal.webgal_assets import install_asset_pack, rewrite_script

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
EXAMPLE_PACK = "builtin:cc0-chronicle"


def make_pack(tmp_path: Path, *, spdx: str = "CC0-1.0", profiles=None) -> Path:
    root = tmp_path / "pack"
    (root / "backgrounds").mkdir(parents=True)
    image = root / "backgrounds" / "archive.png"
    image.write_bytes(PNG)
    (root / "LICENSE").write_text("license\n", encoding="utf-8")
    (root / "NOTICE.md").write_text("notice\n", encoding="utf-8")
    manifest = {
        "$schema": "https://repo2gal.dev/schemas/asset-pack/v1.json",
        "manifestVersion": 1,
        "name": "example-pack",
        "version": "1.0.0",
        "displayName": "Example",
        "description": "A test pack",
        "authors": [{"name": "Tester"}],
        "license": {"spdx": spdx, "file": "LICENSE"},
        "locale": "zh-CN",
        "profiles": profiles or [],
        "theme": {"palette": {"primary": "oklch(50% 0.2 30)"}},
        "assets": {
            "background.archive": {
                "type": "background",
                "file": "backgrounds/archive.png",
                "mimeType": "image/png",
                "width": 1,
                "height": 1,
                "sha256": hashlib.sha256(PNG).hexdigest(),
            }
        },
        "provenance": {"sourceType": "manual", "createdAt": "2026-08-21T00:00:00Z"},
    }
    (root / "repo2gal-pack.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return root


def read_manifest(root: Path) -> dict:
    return json.loads((root / "repo2gal-pack.json").read_text(encoding="utf-8"))


def write_manifest(root: Path, manifest: dict) -> None:
    (root / "repo2gal-pack.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def test_load_valid_pack_and_catalog(tmp_path):
    pack = load_asset_pack(make_pack(tmp_path), public=True)
    assert pack.name == "example-pack"
    assert pack.logical_ids("background") == ["background.archive"]
    assert pack.command_catalog()["changeBg"] == frozenset({"background.archive"})


def test_built_in_cc0_example_passes_public_validation():
    pack = load_asset_pack(EXAMPLE_PACK, public=True)
    assert pack.manifest["license"]["spdx"] == "CC0-1.0"
    assert set(pack.assets) == {
        "background.archive",
        "background.community",
        "character.guide.normal",
        "bgm.archive",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("version", "v1.0"),
        ("locale", "zh_CN"),
    ],
)
def test_schema_rejects_invalid_standard_formats(tmp_path, field, value):
    root = make_pack(tmp_path)
    manifest = read_manifest(root)
    manifest[field] = value
    write_manifest(root, manifest)
    with pytest.raises(AssetPackError, match="Schema"):
        load_asset_pack(root)


def test_schema_rejects_invalid_spdx_and_css_color(tmp_path):
    root = make_pack(tmp_path)
    manifest = read_manifest(root)
    manifest["license"]["spdx"] = "Creative Commons"
    manifest["theme"]["palette"]["primary"] = "definitely-not-a-color"
    write_manifest(root, manifest)
    with pytest.raises(AssetPackError) as exc:
        load_asset_pack(root)
    assert "spdx" in str(exc.value) and "css-color" in str(exc.value)


def test_logical_id_must_start_with_asset_type(tmp_path):
    root = make_pack(tmp_path)
    manifest = read_manifest(root)
    manifest["assets"]["bg.webp"] = manifest["assets"].pop("background.archive")
    write_manifest(root, manifest)
    with pytest.raises(AssetPackError, match="必须以素材类型"):
        load_asset_pack(root)


def test_duplicate_json_key_rejected(tmp_path):
    root = make_pack(tmp_path)
    manifest_file = root / "repo2gal-pack.json"
    text = manifest_file.read_text(encoding="utf-8")
    manifest_file.write_text(text.replace('"version": "1.0.0",', '"version": "1.0.0",\n  "version": "2.0.0",'), encoding="utf-8")
    with pytest.raises(AssetPackError, match="重复键"):
        load_asset_pack(root)


def test_oversized_manifest_is_rejected_by_bounded_reader(tmp_path):
    root = make_pack(tmp_path)
    (root / "repo2gal-pack.json").write_bytes(b"{" + b" " * (MAX_MANIFEST_BYTES + 1))
    with pytest.raises(AssetPackError, match="manifest.*上限"):
        load_asset_pack(root)


def test_hash_mismatch_rejected(tmp_path):
    root = make_pack(tmp_path)
    (root / "backgrounds" / "archive.png").write_bytes(PNG + b"changed")
    with pytest.raises(AssetPackError, match="SHA-256"):
        load_asset_pack(root)


def test_declared_mime_must_match_magic_and_extension(tmp_path):
    root = make_pack(tmp_path)
    manifest = read_manifest(root)
    manifest["assets"]["background.archive"]["mimeType"] = "image/jpeg"
    write_manifest(root, manifest)
    with pytest.raises(AssetPackError, match="扩展名"):
        load_asset_pack(root)


def test_path_traversal_rejected(tmp_path):
    root = make_pack(tmp_path)
    outside = tmp_path / "outside.png"
    outside.write_bytes(PNG)
    manifest = read_manifest(root)
    manifest["assets"]["background.archive"]["file"] = "../outside.png"
    write_manifest(root, manifest)
    with pytest.raises(AssetPackError, match="逃出"):
        load_asset_pack(root)


def test_asset_symlink_rejected(tmp_path):
    root = make_pack(tmp_path)
    image = root / "backgrounds" / "archive.png"
    real = root / "backgrounds" / "real.png"
    image.rename(real)
    image.symlink_to(real.name)
    with pytest.raises(AssetPackError, match="符号链接"):
        load_asset_pack(root)


def test_asset_parent_directory_symlink_rejected(tmp_path):
    root = make_pack(tmp_path)
    outside = tmp_path / "outside"
    (root / "backgrounds").rename(outside)
    (root / "backgrounds").symlink_to(outside, target_is_directory=True)
    with pytest.raises(AssetPackError, match="符号链接"):
        load_asset_pack(root)


def test_public_mode_rejects_license_ref(tmp_path):
    root = make_pack(tmp_path, spdx="LicenseRef-Proprietary")
    assert load_asset_pack(root).name == "example-pack"
    with pytest.raises(AssetPackError, match="公开发布"):
        load_asset_pack(root, public=True)


def test_profile_requirements_are_enforced(tmp_path):
    root = make_pack(tmp_path, profiles=["repo2gal.chronicle"])
    with pytest.raises(AssetPackError, match="Profile") as exc:
        load_asset_pack(root)
    assert "character" in str(exc.value) and "bgm" in str(exc.value)


def test_init_creates_valid_local_skeleton_without_overwrite(tmp_path):
    root = init_asset_pack(tmp_path / "My Pack")
    pack = load_asset_pack(root)
    assert pack.version == "0.1.0"
    assert (root / "NOTICE.md").exists()
    with pytest.raises(AssetPackError, match="必须不存在或为空"):
        init_asset_pack(root)


def test_init_failure_is_wrapped_and_leaves_no_partial_pack(tmp_path, monkeypatch):
    root = tmp_path / "new-pack"
    original = Path.write_text

    def fail_license(self, *args, **kwargs):
        if self.name == "LICENSE":
            raise OSError("disk full")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_license)
    with pytest.raises(AssetPackError, match="无法初始化"):
        init_asset_pack(root)
    assert not root.exists()
    assert not list(tmp_path.glob(".new-pack.init-*"))


def test_rewrite_script_maps_logical_ids_and_keeps_args():
    pack = load_asset_pack(EXAMPLE_PACK)
    script = (
        "changeBg:background.archive -next;\n"
        "changeFigure:character.guide.normal -left;\n"
        "bgm:bgm.archive -volume=60;\n"
        "end;\n"
    )
    out = rewrite_script(script, pack)
    assert "changeBg:background-archive.png -next;" in out
    assert "changeFigure:character-guide-normal.png -left;" in out
    assert "bgm:bgm-archive.ogg -volume=60;" in out


def test_rewrite_script_preserves_webgal_default_assets():
    pack = load_asset_pack(EXAMPLE_PACK)
    script = "changeBg:bg.webp;\nbgm:s_Title.mp3;\nend;\n"
    assert rewrite_script(script, pack) == script


def test_install_rechecks_hash_after_validation(tmp_path, monkeypatch):
    root = make_pack(tmp_path)
    pack = load_asset_pack(root)
    (root / "backgrounds" / "archive.png").write_bytes(PNG + b"changed")
    staging = tmp_path / "staging"
    staging.mkdir()
    monkeypatch.setattr(
        Path,
        "unlink",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("path unlink used")),
    )
    with pytest.raises(PackageError, match="校验后"):
        install_asset_pack(staging, pack)
    assert not (staging / "game" / "background" / "background-archive.png").exists()


def test_install_rechecks_license_material_after_validation(tmp_path):
    root = make_pack(tmp_path)
    pack = load_asset_pack(root)
    (root / "NOTICE.md").write_text("changed notice\n", encoding="utf-8")
    staging = tmp_path / "staging"
    staging.mkdir()
    with pytest.raises(PackageError, match="素材包文件.*校验后"):
        install_asset_pack(staging, pack)
    material = staging / "third_party" / "asset-packs" / "example-pack-1.0.0"
    assert not (material / "NOTICE.md").exists()


def test_install_rejects_symlinked_target_directory(tmp_path):
    pack = load_asset_pack(make_pack(tmp_path))
    staging = tmp_path / "staging"
    outside = tmp_path / "outside"
    outside.mkdir()
    (staging / "game").mkdir(parents=True)
    (staging / "game" / "background").symlink_to(outside, target_is_directory=True)
    with pytest.raises(PackageError, match="安全创建"):
        install_asset_pack(staging, pack)
    assert not list(outside.iterdir())


def test_ai_prompt_is_validated_and_preserved_as_audit_material(tmp_path):
    root = make_pack(tmp_path)
    (root / "generation").mkdir()
    (root / "generation" / "prompts.json").write_text("{}\n", encoding="utf-8")
    manifest = read_manifest(root)
    manifest["provenance"] = {
        "sourceType": "ai-generated",
        "provider": "example",
        "model": "example-v1",
        "generatedAt": "2026-08-21T00:00:00Z",
        "promptFile": "generation/prompts.json",
        "providerTerms": "https://example.test/terms",
        "termsRetrievedAt": "2026-08-21T00:00:00Z",
    }
    write_manifest(root, manifest)
    pack = load_asset_pack(root, public=True)
    assert "generation/prompts.json" in pack.support_files

    staging = tmp_path / "staging"
    staging.mkdir()
    install_asset_pack(staging, pack)
    material = staging / "third_party" / "asset-packs" / "example-pack-1.0.0"
    assert (material / "generation" / "prompts.json").read_text(encoding="utf-8") == "{}\n"


def test_package_installs_assets_notices_and_preserves_template_defaults(tmp_path):
    template = tmp_path / "template"
    (template / "game" / "scene").mkdir(parents=True)
    (template / "game" / "background").mkdir()
    (template / "game" / "bgm").mkdir()
    (template / "index.html").write_text("<html></html>", encoding="utf-8")
    (template / "game" / "background" / "WebGAL_New_Enter_Image.webp").write_bytes(b"title")
    (template / "game" / "bgm" / "s_Title.mp3").write_bytes(b"title music")
    pack = load_asset_pack(EXAMPLE_PACK, public=True)

    out = package(
        "changeBg:background.archive;\nbgm:bgm.archive;\nend;\n",
        tmp_path / "out",
        game_name="Test",
        game_key="key",
        template=template,
        asset_pack=pack,
    )

    script = (out / "game" / "scene" / "start.txt").read_text(encoding="utf-8")
    assert "changeBg:background-archive.png;" in script
    assert "bgm:bgm-archive.ogg;" in script
    assert (out / "game" / "background" / "background-archive.png").exists()
    assert (out / "game" / "figure" / "character-guide-normal.png").exists()
    assert (out / "game" / "bgm" / "bgm-archive.ogg").exists()
    assert (out / "game" / "background" / "WebGAL_New_Enter_Image.webp").exists()
    assert (out / "game" / "bgm" / "s_Title.mp3").exists()
    notices = (out / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "CC0-1.0" in notices and "MPL-2.0" in notices
    assert (out / "third_party" / "WebGAL" / "LICENSE").exists()
    material = out / "third_party" / "asset-packs" / "repo2gal-example-cc0-chronicle-1.0.0"
    assert (material / "LICENSE").exists()
    assert (material / "NOTICE.md").exists()
    assert (material / "repo2gal-pack.json").exists()
