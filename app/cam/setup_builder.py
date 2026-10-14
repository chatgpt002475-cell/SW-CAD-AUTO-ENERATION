"""
CNC Machining Setup Builder
Defines raw workpiece stock dimensions, clearance offsets, and WCS datum.
"""

from typing import Dict, Any

class MachiningSetup:
    def __init__(
        self,
        stock_x_len: float,
        stock_y_len: float,
        stock_z_len: float,
        wcs_origin: str = "TopCenter",  # TopCenter, TopLeft
        material: str = "6061-T6 Aluminum",
        work_offset: str = "G54"
    ):
        self.stock_dims = {
            "x_mm": round(stock_x_len, 2),
            "y_mm": round(stock_y_len, 2),
            "z_mm": round(stock_z_len, 2)
        }
        self.wcs_origin = wcs_origin
        self.material = material
        self.work_offset = work_offset

    @classmethod
    def from_solid_bbox(cls, bbox: Dict[str, Any], padding_xy_mm: float = 6.0, padding_z_top_mm: float = 2.0, material: str = "6061-T6 Aluminum"):
        stock_x = bbox["x_len"] + padding_xy_mm * 2.0
        stock_y = bbox["y_len"] + padding_xy_mm * 2.0
        stock_z = bbox["z_len"] + padding_z_top_mm
        return cls(stock_x, stock_y, stock_z, material=material)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stock_dimensions_mm": self.stock_dims,
            "wcs_origin": self.wcs_origin,
            "material": self.material,
            "work_offset": self.work_offset
        }
