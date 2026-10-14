"""
CNC Machine Configuration
Defines kinematic limits, work envelope, rapid rates, and safety retract planes.
"""

from typing import Dict, Any, Tuple


class MachineConfig:
    def __init__(
        self,
        name: str = "Standard 3-Axis VMC",
        controller: str = "LinuxCNC",
        axes: int = 3,
        x_travel_mm: Tuple[float, float] = (-250.0, 250.0),
        y_travel_mm: Tuple[float, float] = (-150.0, 150.0),
        z_travel_mm: Tuple[float, float] = (-100.0, 150.0),
        max_spindle_rpm: int = 12000,
        max_feed_rate_mm_min: float = 3000.0,
        rapid_rate_mm_min: float = 6000.0,
        safe_clearance_z_mm: float = 5.0,
        retract_plane_z_mm: float = 15.0
    ):
        self.name = name
        self.controller = controller  # LinuxCNC, GRBL, Fanuc, Haas
        self.axes = axes
        self.x_travel = x_travel_mm
        self.y_travel = y_travel_mm
        self.z_travel = z_travel_mm
        self.max_spindle_rpm = max_spindle_rpm
        self.max_feed_rate = max_feed_rate_mm_min
        self.rapid_rate = rapid_rate_mm_min
        self.safe_clearance_z = safe_clearance_z_mm
        self.retract_plane_z = retract_plane_z_mm

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "controller": self.controller,
            "axes": self.axes,
            "x_travel": self.x_travel,
            "y_travel": self.y_travel,
            "z_travel": self.z_travel,
            "max_spindle_rpm": self.max_spindle_rpm,
            "max_feed_rate": self.max_feed_rate,
            "safe_clearance_z": self.safe_clearance_z,
            "retract_plane_z": self.retract_plane_z
        }
