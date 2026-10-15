"""
STL Export Module
Exports validated FreeCAD PartDesign body or OpenCASCADE B-Rep shape
to standard STL mesh for high-performance 3D WebGL rendering.
"""

import os
from typing import Dict, Any


class StlExporter:
    @staticmethod
    def export_stl(body_or_shape, output_filepath: str, tolerance: float = 0.1) -> Dict[str, Any]:
        """
        Exports PartDesign Body or Shape to an STL file.
        """
        if hasattr(body_or_shape, "Shape"):
            shape = body_or_shape.Shape
        else:
            shape = body_or_shape

        abs_out = os.path.abspath(output_filepath)
        os.makedirs(os.path.dirname(abs_out), exist_ok=True)

        # FreeCAD Shape built-in STL export
        shape.exportStl(abs_out)

        if not os.path.exists(abs_out) or os.path.getsize(abs_out) == 0:
            raise IOError(f"STL export failed: file is missing or empty ({abs_out})")

        return {
            "status": "success",
            "filepath": abs_out,
            "filesize_bytes": os.path.getsize(abs_out)
        }
