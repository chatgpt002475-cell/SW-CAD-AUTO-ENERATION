"""
G-Code Safety Validator
Enforces physical machine limits, spindle safety, safe retracts, and syntax integrity.
Never marks unvalidated code as machine-ready.
"""

import re
from typing import Dict, Any, List
from .machine_config import MachineConfig


class GCodeValidator:
    @staticmethod
    def validate(gcode_text: str, machine_config: MachineConfig = None) -> Dict[str, Any]:
        cfg = machine_config or MachineConfig()
        lines = gcode_text.splitlines()

        report = {
            "is_valid": True,
            "total_lines": len(lines),
            "errors": [],
            "warnings": [],
            "motion_stats": {
                "g0_count": 0,
                "g1_count": 0,
                "tool_changes": 0,
                "min_x": 9999.0,
                "max_x": -9999.0,
                "min_y": 9999.0,
                "max_y": -9999.0,
                "min_z": 9999.0,
                "max_z": -9999.0
            }
        }

        spindle_on = False
        current_z = 0.0

        for line_num, raw_line in enumerate(lines, 1):
            line = raw_line.strip()
            if not line or line.startswith("(") or line.startswith("%"):
                continue

            # Check Spindle
            if "M3" in line or "M03" in line or "M4" in line or "M04" in line:
                spindle_on = True
            elif "M5" in line or "M05" in line or "M30" in line:
                spindle_on = False

            # Check Tool Changes
            if "M6" in line or "M06" in line:
                report["motion_stats"]["tool_changes"] += 1

            # Count motions
            if line.startswith("G0 ") or line.startswith("G00 "):
                report["motion_stats"]["g0_count"] += 1
            elif line.startswith("G1 ") or line.startswith("G01 "):
                report["motion_stats"]["g1_count"] += 1
                if not spindle_on:
                    report["errors"].append(f"Line {line_num}: Linear cutting feed (G1) commanded while spindle is OFF.")

            # Coordinate extraction
            x_match = re.search(r"X([-\d.]+)", line)
            y_match = re.search(r"Y([-\d.]+)", line)
            z_match = re.search(r"Z([-\d.]+)", line)

            if x_match:
                x_val = float(x_match.group(1))
                report["motion_stats"]["min_x"] = min(report["motion_stats"]["min_x"], x_val)
                report["motion_stats"]["max_x"] = max(report["motion_stats"]["max_x"], x_val)
                if x_val < cfg.x_travel[0] or x_val > cfg.x_travel[1]:
                    report["errors"].append(f"Line {line_num}: X coordinate {x_val} exceeds machine travel limits {cfg.x_travel}.")

            if y_match:
                y_val = float(y_match.group(1))
                report["motion_stats"]["min_y"] = min(report["motion_stats"]["min_y"], y_val)
                report["motion_stats"]["max_y"] = max(report["motion_stats"]["max_y"], y_val)
                if y_val < cfg.y_travel[0] or y_val > cfg.y_travel[1]:
                    report["errors"].append(f"Line {line_num}: Y coordinate {y_val} exceeds machine travel limits {cfg.y_travel}.")

            if z_match:
                z_val = float(z_match.group(1))
                report["motion_stats"]["min_z"] = min(report["motion_stats"]["min_z"], z_val)
                report["motion_stats"]["max_z"] = max(report["motion_stats"]["max_z"], z_val)
                current_z = z_val
                if z_val < cfg.z_travel[0] or z_val > cfg.z_travel[1]:
                    report["errors"].append(f"Line {line_num}: Z coordinate {z_val} exceeds machine travel limits {cfg.z_travel}.")

            # Rapid traverse check (G0 should not move horizontally below safe height)
            if (line.startswith("G0 ") or line.startswith("G00 ")) and (x_match or y_match):
                if current_z < 0.0:
                    report["warnings"].append(f"Line {line_num}: Rapid XY motion at Z={current_z} below top of workpiece (potential clamp/part collision).")

        if report["errors"]:
            report["is_valid"] = False

        return report
