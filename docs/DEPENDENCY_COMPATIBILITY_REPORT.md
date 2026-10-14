# Dependency and Environment Compatibility Report

## System Environment
- **Host Operating System**: Microsoft Windows 11 Pro (64-bit)
- **Primary CAD Platform**: FreeCAD 1.1.4 (Git shallow build 2026-09-28)
- **FreeCAD Binary Location**: `C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe`
- **FreeCAD Bundled Python Runtime**: Python 3.11.14 (packaged by conda-forge, MSC v.1944)
- **System Python Runtime**: Python 3.14.2 (64-bit)

## Verified Workbenches and Core Libraries

| Component / Library | Version / Status | Verified Capability |
| :--- | :--- | :--- |
| **FreeCAD Core (`FreeCAD`, `Part`)** | 1.1.4 | Document management, OCCT B-Rep solid generation, STEP import/export |
| **`PartDesign` & `Sketcher`** | 1.1.4 | Parametric sketches, constraints (`Coincident`, `DistanceX`, `Radius`), `Pad`, `Pocket`, `Fillet` |
| **`CAM` / `Path` Workbench** | 1.1.4 | Modern FreeCAD 1.1 CAM engine: `Path.Main`, `Path.Op`, `Path.Post`, `Path.Tool` |
| **`OpenCASCADE Technology (OCCT)`** | 8.0.1 / 7.8 | Manifold B-Rep kernel, advanced surface representation, Boolean difference/fuse |
| **`OpenCV (cv2)`** | 5.0.0.93 | Bilateral filtering, Otsu thresholding, contour extraction, circle fitting |
| **`NumPy`** | 2.4.6 / 1.26.4 | Vector math, matrix coordinate transformations, contour analysis |
| **`PySide6`** | 6.x | Native desktop GUI application, toolbars, splitters, tables |
| **`TechDraw`** | 1.1.4 | 2D technical drafting and drawing projection |

## Compatibility Notes
1. **FreeCAD 1.1 Modern CAM Hierarchy**:
   FreeCAD 1.0 and 1.1 transitioned the classic `PathScripts` workbench structure into the new `CAM` module (`C:\Program Files\FreeCAD 1.1\Mod\CAM`). The application cleanly imports from `Path.Main`, `Path.Op`, `Path.Post`, and `Path.Tool`.
2. **Dual Python Environments**:
   FreeCAD's embedded Python runtime (`C:\Program Files\FreeCAD 1.1\bin\python.exe`) was configured with `opencv-python` to provide single-process execution for CAD, CAM, OpenCV, and PySide6.
