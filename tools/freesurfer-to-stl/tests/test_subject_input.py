import json
import subprocess
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest
import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from subject_input import (NON_CORTEX_GROUPS, extract_group, prepare_subject,
                           subject_inputs, voxel_to_surface_ras)


@pytest.fixture
def subject(tmp_path):
    path = tmp_path / "subjects" / "sample"
    (path / "mri").mkdir(parents=True)
    (path / "surf").mkdir()
    affine = np.array([[0, 0, -1.2, 83], [-.8, 0, 0, 27], [0, 1.1, 0, -45], [0, 0, 0, 1]])
    data = np.zeros((20, 22, 24), dtype=np.int16)
    data[2:8, 3:9, 4:10] = 10
    data[12:15, 15:19, 16:20] = 49
    data[1:4, 17:20, 1:4] = 24  # CSF must not become a mesh.
    nib.save(nib.MGHImage(data, affine), path / "mri" / "aseg.mgz")
    nib.save(nib.MGHImage(np.zeros_like(data), affine), path / "mri" / "orig.mgz")
    for hemi, x in (("lh", -10), ("rh", 10)):
        mesh = trimesh.creation.icosphere(subdivisions=2, radius=8)
        mesh.apply_translation([x, 0, 0])
        nib.freesurfer.write_geometry(str(path / "surf" / f"{hemi}.pial.T1"), mesh.vertices, mesh.faces)
    return path


def test_affine_matches_surface_ras_and_resampled_grid(subject):
    reference = nib.load(subject / "mri" / "orig.mgz")
    seg = nib.load(subject / "mri" / "aseg.mgz")
    np.testing.assert_allclose(voxel_to_surface_ras(seg, reference), reference.header.get_vox2ras_tkr(), atol=1e-5)
    grid = np.eye(4)
    grid[:3, :3] *= .5
    grid[:3, 3] = [3, 4, 5]
    resampled = nib.Nifti1Image(np.zeros((40, 44, 48)), reference.affine @ grid)
    np.testing.assert_allclose(voxel_to_surface_ras(resampled, reference), reference.header.get_vox2ras_tkr() @ grid, atol=1e-5)


def test_native_export_excludes_csf_preserves_coordinates_and_records_absent_labels(subject, tmp_path):
    output = tmp_path / "export"
    # A stale file must never be returned as a member of the current export.
    output.mkdir()
    (output / "aseg.final.13.stl").write_text("stale")
    generated = prepare_subject(subject, output)
    assert generated == ["aseg.final.10.stl", "aseg.final.49.stl"]
    assert not (output / "aseg.final.24.stl").exists()
    manifest = json.loads((output / "source_manifest.json").read_text())
    assert 251 in manifest["missing_labels"]
    reference = nib.load(subject / "mri" / "orig.mgz")
    expected_center = nib.affines.apply_affine(reference.header.get_vox2ras_tkr(), [4.5, 5.5, 6.5])
    mesh = trimesh.load_mesh(output / "aseg.final.10.stl")
    assert mesh.is_volume
    np.testing.assert_allclose(mesh.bounds.mean(axis=0), expected_center, atol=1e-5)
    left = trimesh.load_mesh(output / "lh.pial.stl")
    np.testing.assert_allclose(left.bounds.mean(axis=0), [-10, 0, 0], atol=1e-5)


def test_segmentation_selection_and_missing_surface(subject):
    original = subject / "mri" / "aseg.mgz"
    fallback = subject / "mri" / "aparc.DKTatlas+aseg.deep.mgz"
    fallback.write_bytes(original.read_bytes())
    assert subject_inputs(subject)[3] == original
    original.unlink()
    assert subject_inputs(subject)[3] == fallback
    (subject / "surf" / "lh.pial.T1").unlink()
    with pytest.raises(ValueError, match="surface pipeline"):
        subject_inputs(subject)


def test_source_folder_protected(subject):
    with pytest.raises(ValueError, match="outside"):
        prepare_subject(subject, subject / "new-output")
    assert not (subject / "new-output").exists()


def test_touching_labels_have_closed_combined_outline(subject, tmp_path):
    path = subject / "mri" / "aseg.mgz"
    image = nib.load(path)
    data = np.zeros(image.shape, np.int16)
    data[2:7, 3:10, 4:12] = 10
    data[7:12, 3:10, 4:12] = 11
    nib.save(nib.MGHImage(data, image.affine), path)
    output = tmp_path / "touching"
    prepare_subject(subject, output)
    combined = trimesh.load_mesh(output / "non-cortex.stl")
    assert combined.is_volume
    assert len(combined.split()) == 1
    assert len(combined.faces) < sum(len(trimesh.load_mesh(p).faces) for p in output.glob("aseg.final.*.stl"))


def test_preserves_disconnected_components_at_volume_border():
    data = np.zeros((12, 12, 12), np.int16)
    data[0:3, 0:3, 0:3] = 10
    data[8:12, 8:12, 8:12] = 10
    transform = np.diag([-2., 1., 1.5, 1.])
    mesh, _ = extract_group(data, transform, (10,))
    assert mesh.is_volume
    assert len(mesh.split()) == 2
    np.testing.assert_allclose(mesh.bounds, [[-23, -.5, -.75], [1, 11.5, 17.25]])


def test_native_cli_and_legacy_stl_mode(subject, tmp_path):
    # Populate all groups so the same fixture can test the strict legacy mode.
    path = subject / "mri" / "aseg.mgz"
    image = nib.load(path)
    data = np.zeros(image.shape, np.int16)
    for index, group in enumerate(NON_CORTEX_GROUPS):
        x = (index % 4) * 5 + 1
        y = (index // 4) * 5 + 1
        data[x:x+3, y:y+3, 4:7] = group[0]
    nib.save(nib.MGHImage(data, image.affine), path)
    native_output = tmp_path / "native.stl"
    command = [sys.executable, str(ROOT / "3Dprintprep.py")]
    result = subprocess.run(command + [str(subject.parent), str(native_output), "--subject", subject.name], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert trimesh.load_mesh(native_output).is_watertight
    legacy_output = tmp_path / "legacy.stl"
    result = subprocess.run(command + ["--i", str(tmp_path / "native_surfaces"), "--o", str(legacy_output), "--input-type", "brainprint"], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    native = trimesh.load_mesh(native_output)
    legacy = trimesh.load_mesh(legacy_output)
    np.testing.assert_allclose(native.bounds, legacy.bounds)
    assert len(native.faces) == len(legacy.faces)


def test_check_input_creates_no_outputs(subject, tmp_path):
    output = tmp_path / "check.stl"
    result = subprocess.run([sys.executable, str(ROOT / "3Dprintprep.py"), str(subject), str(output), "--check-input"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert not output.exists()
    assert not (tmp_path / "check_surfaces").exists()
