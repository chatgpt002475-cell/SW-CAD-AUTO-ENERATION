# AI-Powered Image-to-3D Parametric CAD and CNC CAM Studio
## Professional Engineering User Guide

---

## 1. Overview & Architecture

This application provides a complete engineering pipeline that bridges **2D raster drawings/images**, **3D parametric B-Rep CAD solids**, and **CNC machining G-code**:

```text
2D IMAGE INPUT
      ↓
IMAGE ANALYSIS & CALIBRATION (OpenCV + Douglas-Peucker)
      ↓
FEATURE RECOGNITION (Base Plates, Holes, Pockets, Flanges, Slots)
      ↓
PARAMETRIC CAD RECONSTRUCTION (FreeCAD 1.1 PartDesign & Sketcher)
      ↓
SOLID GEOMETRY VALIDATION (OpenCASCADE Topology & Manifold Checks)
      ↓
STEP EXPORT & RE-IMPORT CHECK (ISO 10303 AP214 / AP242)
      ↓
CNC CAM OPERATION PLANNING (Stock, Tools, Facing, Pocketing, Drilling, Profiling)
      ↓
TOOLPATH SIMULATION & G-CODE POSTPROCESSING (LinuxCNC, GRBL, Fanuc, Haas)
```

---

## 2. Launching the Application

### Method 1: Command Line (CLI Mode)
Run through FreeCAD's Python environment:
```powershell
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" app/main.py path/to/drawing.png -w 120.0 -t 12.0 --flange-height 35.0 -s part.step -p part.FCStd -g toolpath.nc -c LinuxCNC
```

### Method 2: Native Desktop GUI (PySide6)
```powershell
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" app/ui/desktop_app.py
```

### Method 3: Automated Test Suite (Acceptance Tests A through F)
```powershell
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" tests/test_all_criteria.py
```

---

## 3. Step-by-Step Engineering Workflow

### Step 1: Image Import & Calibration
- Supported image formats: `.png`, `.jpg`, `.jpeg`, `.bmp`, `.tiff`.
- Provide a physical reference width (`Target Width in mm`).
- The calibrator computes the exact `mm_per_pixel` ratio. **Pixels are never silently assumed to equal millimeters.**

### Step 2: Feature Recognition
- **Base Profile**: Outer boundary traced with Otsu thresholding and regularized with Douglas-Peucker polygon reduction.
- **Holes**: Detected through circularity scoring ($4\pi A / P^2 \ge 0.85$). Analytical circles are fitted rather than segmented meshes.
- **Slots & Recesses**: Converted into closed planar wires.

### Step 3: Parametric CAD Construction
- Built using native FreeCAD `PartDesign::Body` and `Sketcher::SketchObject`.
- Construction steps:
  1. `BaseSketch` → `BasePad` (Extrusion to specified thickness).
  2. `FlangeSketch` → `FlangePad` (Upright or angled secondary flange).
  3. `HolePocket` (Through-holes or blind holes).
  4. `RecessedPocket` (Internal pockets).
  5. `EdgeFillet` / `EdgeChamfer`.
- Feature properties are fully editable and trigger live parametric recomputes.

### Step 4: Solid Validation & STEP Export
- Verifies manifold topology, positive non-zero volume, shell closure, face count, and edge count.
- Exports standard ISO 10303 **STEP AP214 / AP242** solids.
- Performs a round-trip re-import check comparing the re-read shape volume with the source solid.
- Saves native `.FCStd` project files with metadata sidecars.

### Step 5: CNC CAM Toolpaths & G-Code Generation
- **Stock Setup**: Automatically calculates raw workpiece dimensions from bounding box + clearance padding.
- **WCS**: Configured at G54 top-center datum.
- **Operations**:
  - `Op1_Facing`: Surfaces stock top to $Z=0$ using face mill.
  - `Op2_Drilling`: Peck drilling cycles for all recognized holes.
  - `Op3_PocketMilling`: Clears internal cavities and slots.
  - `Op4_2DProfiling`: Perimeter finish contouring with multiple stepdown passes.
- **Simulation**: Computes travel distances, rapid vs feed motion, and estimated machining cycle times.
- **Postprocessing**: Exports validated G-code formatted for **LinuxCNC**, **GRBL**, **Fanuc**, or **Haas**.
- **Safety**: Automatically verifies spindle activation, safe retract heights, and physical machine travel limits.
