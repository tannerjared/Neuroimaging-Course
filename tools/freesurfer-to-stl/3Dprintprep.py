import os
import sys
import argparse

# ---------------------------------------------------------
# Smoothing parameters
# ---------------------------------------------------------

CORTEX_SMOOTHING_STEPS = 100

# VTK windowed-sinc smoothing for non-cortical structures
NON_CORTEX_SMOOTHING_ITERATIONS = 30

# Lower = more smoothing.
# Start at 0.05.
# If still blocky: 0.02, then 0.01.
NON_CORTEX_PASSBAND = 0.2

# ---------------------------------------------------------
# Check if the required packages are installed
# ---------------------------------------------------------
try:
    import pymeshlab
    import vtk
except ImportError as e:
    print(f"Error: {e}")
    print("Please install the required packages using:")
    print("pip install -r requirements.txt")
    sys.exit(1)


def convert_vtk_to_stl(input_filename, output_filename):
    """Convert a VTK surface file to STL."""

    vtk_reader = vtk.vtkDataSetReader()
    vtk_reader.SetFileName(input_filename)
    vtk_reader.Update()

    vtk_to_stl = vtk.vtkDataSetSurfaceFilter()
    vtk_to_stl.SetInputConnection(vtk_reader.GetOutputPort())
    vtk_to_stl.Update()

    stl_writer = vtk.vtkSTLWriter()
    stl_writer.SetFileName(output_filename)
    stl_writer.SetInputConnection(vtk_to_stl.GetOutputPort())
    stl_writer.Write()

def smooth_stl_windowed_sinc(
    input_filename,
    output_filename,
    iterations=30,
    passband=0.05
):
    """
    Smooth an STL using VTK windowed-sinc smoothing.

    This is intended to reduce voxel/marching-cubes stair-step artifacts
    while preserving overall surface geometry better than repeated
    Laplacian smoothing.
    """

    # Read STL
    reader = vtk.vtkSTLReader()
    reader.SetFileName(input_filename)
    reader.Update()

    # Clean duplicate/coincident points
    cleaner = vtk.vtkCleanPolyData()
    cleaner.SetInputConnection(reader.GetOutputPort())
    cleaner.Update()

    # Ensure triangular polygons
    triangulate = vtk.vtkTriangleFilter()
    triangulate.SetInputConnection(cleaner.GetOutputPort())
    triangulate.Update()

    # Windowed-sinc smoothing
    smoother = vtk.vtkWindowedSincPolyDataFilter()
    smoother.SetInputConnection(triangulate.GetOutputPort())

    smoother.SetNumberOfIterations(iterations)
    smoother.SetPassBand(passband)

    # Better numerical stability
    smoother.NormalizeCoordinatesOn()

    # Allow smoothing across the voxel-derived mesh
    smoother.FeatureEdgeSmoothingOff()
    smoother.BoundarySmoothingOn()
    smoother.NonManifoldSmoothingOn()

    # Nuttall is VTK's recommended window
    smoother.SetWindowFunctionToNuttall()

    smoother.Update()

    # Write smoothed STL
    writer = vtk.vtkSTLWriter()
    writer.SetFileName(output_filename)
    writer.SetInputConnection(smoother.GetOutputPort())
    writer.Write()

def combine_cortex(input_directory):
    """Combine left and right pial surfaces and create a smoothed cortex."""

    ms = pymeshlab.MeshSet()

    # Load left and right pial surfaces
    ms.load_new_mesh(
        os.path.join(input_directory, "lh.pial.stl")
    )

    ms.load_new_mesh(
        os.path.join(input_directory, "rh.pial.stl")
    )

    # Merge hemispheres
    ms.apply_filter(
        "generate_by_merging_visible_meshes",
        mergevertices=True
    )

    # Save unsmoothed cortex
    output_cortex = os.path.join(
        input_directory,
        "cortex.stl"
    )

    ms.save_current_mesh(output_cortex)

    # Smooth cortex
    percentage_delta = pymeshlab.PercentageValue(0.1)

    ms.apply_filter(
        "apply_coord_laplacian_smoothing_scale_dependent",
        stepsmoothnum=CORTEX_SMOOTHING_STEPS,
        delta=percentage_delta
    )

    # Save smoothed cortex
    output_cortex_smoothed = os.path.join(
        input_directory,
        "cortex_smoothed.stl"
    )

    ms.save_current_mesh(output_cortex_smoothed)


def combine_non_cortex(input_directory, non_cortex_files=None, precombined=False):
    """Combine all non-cortical structures and smooth them together."""

    ms = pymeshlab.MeshSet()

    # Cerebellum, brainstem, subcortical structures, and corpus callosum.
    # aseg.final.14_24.stl is intentionally excluded because it contains
    # CSF and can generate an unwanted shell around the cortex.
    if non_cortex_files is None:
        non_cortex_files = [
            "aseg.final.7_8_16_46_47.stl", "aseg.final.10.stl",
            "aseg.final.11_12_26.stl", "aseg.final.13.stl",
            "aseg.final.17.stl", "aseg.final.18.stl", "aseg.final.28.stl",
            "aseg.final.49.stl", "aseg.final.50_51_58.stl", "aseg.final.52.stl",
            "aseg.final.53.stl", "aseg.final.54.stl", "aseg.final.60.stl",
            "aseg.final.251_252_253_254_255.stl"
        ]


    output_non_cortex = os.path.join(
        input_directory,
        "non-cortex.stl"
    )
    if not precombined:
        # Legacy BrainPrint inputs are already tessellated. Native input instead
        # provides a single isosurface of the selected labels' union.
        for filename in non_cortex_files:
            ms.load_new_mesh(os.path.join(input_directory, filename))
        ms.apply_filter("generate_by_merging_visible_meshes", mergevertices=True)
        ms.save_current_mesh(output_non_cortex)

    # Destination for windowed-sinc smoothed mesh
    output_non_cortex_smoothed = os.path.join(
        input_directory,
        "non-cortex_smoothed.stl"
    )

    print(
        "Applying VTK windowed-sinc smoothing "
        f"({NON_CORTEX_SMOOTHING_ITERATIONS} iterations, "
        f"passband={NON_CORTEX_PASSBAND})..."
    )

    smooth_stl_windowed_sinc(
        output_non_cortex,
        output_non_cortex_smoothed,
        iterations=NON_CORTEX_SMOOTHING_ITERATIONS,
        passband=NON_CORTEX_PASSBAND
    )


def combine_and_save_brain(
    input_directory,
    output_filename
):
    """Combine the smoothed cortex and non-cortex meshes."""

    ms = pymeshlab.MeshSet()

    ms.load_new_mesh(
        os.path.join(
            input_directory,
            "cortex_smoothed.stl"
        )
    )

    ms.load_new_mesh(
        os.path.join(
            input_directory,
            "non-cortex_smoothed.stl"
        )
    )

    # Merge only; no additional smoothing
    ms.apply_filter(
        "generate_by_merging_visible_meshes",
        mergevertices=True
    )

    # Create destination directory if necessary
    output_directory = os.path.dirname(
        os.path.abspath(
            output_filename
        )
    )

    os.makedirs(
        output_directory,
        exist_ok=True
    )

    ms.save_current_mesh(
        output_filename
    )


def main():
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description="Export a FastSurfer/FreeSurfer subject or FSQC BrainPrint surfaces to STL."
    )
    parser.add_argument("input_directory", nargs="?", help="Subject folder or BrainPrint surfaces folder")
    parser.add_argument("output_filename", nargs="?", help="Final combined STL filename")
    parser.add_argument("--i", "--input", dest="input_option")
    parser.add_argument("--o", "--output", dest="output_option")
    parser.add_argument("--input-type", choices=("auto", "subject", "brainprint"), default="auto")
    parser.add_argument("--subject", help="Subject ID when input is a subjects directory")
    parser.add_argument("--segmentation", help="Override segmentation file in native subject mode")
    parser.add_argument("--intermediate-dir", help="Native-mode intermediate output directory")
    parser.add_argument("--check-input", action="store_true", help="Check required inputs without exporting")
    args = parser.parse_args()
    if args.input_directory and args.input_option or args.output_filename and args.output_option:
        parser.error("Use positional paths or --i/--o, not both")
    input_value = args.input_option or args.input_directory
    output_value = args.output_option or args.output_filename
    if not input_value or (not output_value and not args.check_input):
        parser.error("An input directory and output STL filename are required")
    input_directory = Path(input_value).expanduser().resolve()
    if args.subject:
        if Path(args.subject).name != args.subject or args.subject in (".", ".."):
            parser.error("--subject must be a single subject directory name")
        input_directory /= args.subject
    if not input_directory.is_dir():
        parser.error(f"Input directory does not exist: {input_directory}")
    native = args.input_type == "subject" or (
        args.input_type == "auto" and (input_directory / "mri").is_dir())
    if not native and any((args.subject, args.segmentation, args.intermediate_dir)):
        parser.error("--subject, --segmentation and --intermediate-dir require native subject input")
    if not native and not any(input_directory.glob("*.vtk")) and not any(input_directory.glob("*.stl")):
        parser.error("No BrainPrint surfaces found. For a subjects directory, add --subject SUBJECT_ID")
    output_filename = Path(output_value).expanduser().resolve() if output_value else None
    if output_filename and output_filename.suffix.lower() != ".stl":
        parser.error("The output filename must end with .stl")
    non_cortex_files = None
    try:
        if native:
            from subject_input import subject_inputs, prepare_subject
            subject, surfaces, reference, segmentation = subject_inputs(input_directory, args.segmentation)
            print(f"Native subject: {subject}\nSegmentation: {segmentation}", flush=True)
            if output_filename and (output_filename == subject or subject in output_filename.parents):
                parser.error("Put the output STL outside the source subject directory")
            if args.check_input:
                print("Both pial surfaces, reference volume and segmentation are present.")
                return
            intermediate = (Path(args.intermediate_dir).expanduser().resolve() if args.intermediate_dir
                            else output_filename.parent / (output_filename.stem + "_surfaces"))
            non_cortex_files = prepare_subject(subject, intermediate, args.segmentation)
            input_directory = intermediate
        else:
            required = ["lh.pial", "rh.pial", "aseg.final.7_8_16_46_47", "aseg.final.10",
                        "aseg.final.11_12_26", "aseg.final.13", "aseg.final.17", "aseg.final.18",
                        "aseg.final.28", "aseg.final.49", "aseg.final.50_51_58", "aseg.final.52",
                        "aseg.final.53", "aseg.final.54", "aseg.final.60", "aseg.final.251_252_253_254_255"]
            missing = [name for name in required if not any(
                (input_directory / (name + ext)).is_file() for ext in (".vtk", ".stl"))]
            if missing:
                parser.error("Missing BrainPrint surfaces: " + ", ".join(missing))
            if args.check_input:
                print("Required BrainPrint surfaces are present.")
                return
            for vtk_path in sorted(input_directory.glob("*.vtk")):
                print(f"Converting: {vtk_path.name}", flush=True)
                convert_vtk_to_stl(str(vtk_path), str(vtk_path.with_suffix(".stl")))
        print("Combining and smoothing cortex...", flush=True)
        combine_cortex(str(input_directory))
        print("Combining and smoothing non-cortex structures...", flush=True)
        combine_non_cortex(str(input_directory), non_cortex_files, precombined=native)
        print("Combining cortex and non-cortex meshes...", flush=True)
        combine_and_save_brain(str(input_directory), str(output_filename))
        if native:
            from subject_input import validate_native_outputs
            print("Checking saved mesh topology...", flush=True)
            validate_native_outputs(input_directory, output_filename)
    except (ValueError, OSError, ImportError) as error:
        parser.error(str(error))
    print(f"Finished: {output_filename}", flush=True)


if __name__ == "__main__":
    main()
