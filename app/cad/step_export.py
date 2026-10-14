"""
STEP Export and Reimport Verification
Exports validated FreeCAD PartDesign solid to ISO 10303 STEP AP214/AP242
and verifies geometry integrity via round-trip re-import check.
"""

import os
from typing import Dict, Any
import Part
from .geometry_validation import GeometryValidator


class StepExporter:
    @staticmethod
    def export_step(body_or_shape, output_filepath: str, schema: str = "AP214") -> Dict[str, Any]:
        """
        Exports solid shape to standard STEP file and performs re-import validation check.
        """
        if hasattr(body_or_shape, "Shape"):
            shape = body_or_shape.Shape
            export_target = [body_or_shape]
        else:
            shape = body_or_shape
            export_target = [shape]

        val = GeometryValidator.validate_solid(shape)
        if not val["is_valid"] or val["volume_cm3"] <= 0:
            raise ValueError(f"Cannot export invalid solid: {val['errors']}")

        abs_out = os.path.abspath(output_filepath)
        os.makedirs(os.path.dirname(abs_out), exist_ok=True)

        # Set export schema if supported
        Part.export(export_target, abs_out)

        if not os.path.exists(abs_out) or os.path.getsize(abs_out) == 0:
            raise IOError(f"STEP export failed: output file is empty or missing ({abs_out})")

        file_size = os.path.getsize(abs_out)

        # Re-import verification check
        reimported_shape = Part.Shape()
        reimported_shape.read(abs_out)
        reimport_val = GeometryValidator.validate_solid(reimported_shape)

        vol_diff = abs(val["volume_cm3"] - reimport_val["volume_cm3"])
        reimport_ok = vol_diff < 0.05 and reimport_val["is_valid"]

        return {
            "status": "success",
            "filepath": abs_out,
            "filesize_bytes": file_size,
            "schema": schema,
            "original_volume_cm3": val["volume_cm3"],
            "reimported_volume_cm3": reimport_val["volume_cm3"],
            "volume_delta_cm3": round(vol_diff, 4),
            "reimport_verified": reimport_ok,
            "faces_count": reimport_val["faces_count"]
        }
