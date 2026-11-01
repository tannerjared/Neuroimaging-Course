"""Read native FastSurfer/FreeSurfer subjects in shared surface RAS millimetres."""
import json
from pathlib import Path

import nibabel as nib
import numpy as np
import trimesh
from skimage.measure import marching_cubes


# Match the existing BrainPrint non-cortex groups; deliberately exclude CSF.
NON_CORTEX_GROUPS = (
    (7, 8, 16, 46, 47), (10,), (11, 12, 26), (13,), (17,), (18,), (28,),
    (49,), (50, 51, 58), (52,), (53,), (54,), (60,), (251, 252, 253, 254, 255),
)
SEGMENTATIONS = (
    "aseg.mgz", "aparc.DKTatlas+aseg.mapped.mgz",
    "aparc.DKTatlas+aseg.deep.withCC.mgz", "aseg.auto_noCCseg.mgz",
    "aparc.DKTatlas+aseg.deep.mgz",
)


def subject_inputs(subject, segmentation=None):
    """Resolve inputs without changing the subject or creating outputs."""
    subject = Path(subject).resolve()
    surfaces = []
    for hemi in ("lh", "rh"):
        candidates = [subject / "surf" / f"{hemi}.pial",
                      subject / "surf" / f"{hemi}.pial.T1"]
        surface = next((p for p in candidates if p.is_file()), None)
        if surface is None:
            raise ValueError(
                f"Missing {hemi}.pial (or {hemi}.pial.T1) in {subject / 'surf'}. "
                "Run the FastSurfer surface pipeline first; --seg_only output "
                "cannot supply the cortical surface.")
        surfaces.append(surface)
    reference = subject / "mri" / "orig.mgz"
    if not reference.is_file():
        raise ValueError(f"Missing surface reference volume: {reference}")
    candidates = ([Path(segmentation).resolve()] if segmentation else
                  [subject / "mri" / name for name in SEGMENTATIONS])
    seg = next((p for p in candidates if p.is_file()), None)
    if seg is None:
        raise ValueError("No supported segmentation found. Checked: " +
                         ", ".join(str(p) for p in candidates))
    return subject, surfaces, reference, seg


def voxel_to_surface_ras(segmentation, reference):
    """Map segmentation voxels into the pial reference's tkregister RAS frame.

    The scanner-RAS bridge also handles a segmentation on a different grid.
    Using segmentation.affine alone would misalign it with the pial surfaces.
    """
    return (reference.header.get_vox2ras_tkr() @
            np.linalg.inv(reference.affine) @ segmentation.affine)


def extract_group(data, transform, ids):
    mask = np.isin(data, ids)
    points = np.argwhere(mask)
    if not len(points):
        return None, None
    low, high = points.min(axis=0), points.max(axis=0) + 1
    cropped = mask[tuple(slice(a, b) for a, b in zip(low, high))]
    padded = np.pad(cropped, 1).astype(np.float32)
    # Resolve exact half-voxel saddle ties without removing disconnected anatomy.
    for level in (0.5, 0.5001):
        vertices, faces, _, _ = marching_cubes(
            padded, level=level, allow_degenerate=False)
        vertices = nib.affines.apply_affine(transform, vertices + low - 1)
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
        if mesh.volume < 0:
            mesh.invert()
        if mesh.is_volume and np.isfinite(mesh.vertices).all():
            return mesh, level
    raise ValueError(f"Labels {ids} did not produce a closed, consistently wound mesh")


def prepare_subject(subject, output_dir, segmentation=None):
    subject, surfaces, reference_path, seg_path = subject_inputs(subject, segmentation)
    output_dir = Path(output_dir).resolve()
    if output_dir == subject or subject in output_dir.parents:
        raise ValueError("Put exported meshes outside the source subject directory")
    reference = nib.load(reference_path)
    segmentation_image = nib.load(seg_path)
    data = np.asanyarray(segmentation_image.dataobj)
    if data.ndim != 3 or not np.isfinite(data).all() or not np.equal(data, np.rint(data)).all():
        raise ValueError("Segmentation must be a finite 3D integer-label image")
    transform = voxel_to_surface_ras(segmentation_image, reference)
    if not np.isfinite(transform).all() or abs(np.linalg.det(transform[:3, :3])) < 1e-9:
        raise ValueError("Invalid voxel-to-surface transform")

    # Read and check both hemispheres before writing any files.
    pial_meshes = []
    for path in surfaces:
        vertices, faces = nib.freesurfer.read_geometry(str(path))
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        if not mesh.is_watertight or not mesh.is_winding_consistent or not np.isfinite(vertices).all():
            raise ValueError(f"Pial surface is not a finite closed mesh: {path}")
        if mesh.volume < 0:
            mesh.invert()
        pial_meshes.append(mesh)

    output_dir.mkdir(parents=True, exist_ok=True)
    for hemi, mesh in zip(("lh", "rh"), pial_meshes):
        mesh.export(output_dir / f"{hemi}.pial.stl")
    report = {
        "subject": str(subject), "segmentation": str(seg_path),
        "reference_volume": str(reference_path),
        "pial_surfaces": [str(p) for p in surfaces],
        "coordinate_frame": "FreeSurfer surface (tkregister) RAS", "units": "mm",
        "segmentation_voxel_to_surface_ras": transform.tolist(),
        "groups": [], "missing_labels": [],
        "note": "Meshes retain anatomical coordinates. Combined STL is a collection "
                "of shells, not a boolean union or a guarantee of printability.",
    }
    present = set(np.unique(data).astype(int))
    generated = []
    for ids in NON_CORTEX_GROUPS:
        missing = [i for i in ids if i not in present]
        report["missing_labels"].extend(missing)
        mesh, level = extract_group(data, transform, ids)
        if mesh is None:
            print(f"Skipping absent segmentation labels: {ids}", flush=True)
            continue
        filename = "aseg.final." + "_".join(map(str, ids)) + ".stl"
        mesh.export(output_dir / filename)
        generated.append(filename)
        report["groups"].append({
            "file": filename, "labels": list(ids), "missing_labels": missing,
            "marching_cubes_level": level, "faces": len(mesh.faces),
            "watertight": bool(mesh.is_watertight),
        })
        print(f"Exported {filename}", flush=True)
    if not generated:
        raise ValueError("Segmentation contains none of the supported non-cortex labels")
    # Adjacent labels share half-voxel boundary vertices. Concatenating the
    # individual meshes can weld these into edges with more than two faces.
    # Extract the union of the SAME labels before smoothing the combined part.
    combined, level = extract_group(data, transform, tuple(
        label for group in NON_CORTEX_GROUPS for label in group))
    combined.export(output_dir / "non-cortex.stl")
    report["combined_non_cortex"] = {
        "method": "isosurface of union of selected segmentation labels",
        "marching_cubes_level": level, "faces": len(combined.faces),
        "watertight": bool(combined.is_watertight),
    }
    if report["missing_labels"]:
        print(f"Labels absent from this segmentation: {report['missing_labels']}", flush=True)
    (output_dir / "source_manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    return generated


def validate_native_outputs(output_dir, output_filename):
    """Check saved meshes, including topology after smoothing and STL welding."""
    output_dir = Path(output_dir)
    results = []
    for path in (output_dir / "cortex_smoothed.stl",
                 output_dir / "non-cortex_smoothed.stl", Path(output_filename)):
        mesh = trimesh.load_mesh(path)
        if not mesh.is_volume or not np.isfinite(mesh.vertices).all():
            raise ValueError(f"Exported mesh is not a finite, closed, consistently wound solid: {path}")
        results.append({"file": str(path), "faces": len(mesh.faces),
                        "watertight": bool(mesh.is_watertight),
                        "winding_consistent": bool(mesh.is_winding_consistent),
                        "bounds_mm": mesh.bounds.tolist(), "size_mm": mesh.extents.tolist()})
    manifest_path = output_dir / "source_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["output_validation"] = results
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
