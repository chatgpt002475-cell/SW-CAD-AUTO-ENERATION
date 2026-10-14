"""
Multi-Controller G-Code Postprocessor
Generates controller-specific G-code: LinuxCNC, GRBL, Fanuc, and Haas dialects.
"""

from typing import List, Dict, Any
from datetime import datetime


class GCodePostprocessor:
    def __init__(self, controller: str = "LinuxCNC"):
        self.controller = controller.upper()

    def postprocess(self, operations: List[Dict[str, Any]], program_name: str = "PART_1001") -> str:
        lines = []

        # Header
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"%")
        lines.append(f"(PROGRAM: {program_name})")
        lines.append(f"(CONTROLLER: {self.controller})")
        lines.append(f"(GENERATED: {date_str})")
        lines.append(f"(SAFETY: VERIFY SETUP AND TOOLING BEFORE CYCLE START)")
        lines.append(f"")

        # Preamble
        if self.controller in ("FANUC", "HAAS"):
            lines.append(f"O1001 ({program_name})")
            lines.append("G21 (Metric Units)")
            lines.append("G90 (Absolute Programming)")
            lines.append("G17 (XY Working Plane)")
            lines.append("G40 G49 G80 (Cancel Compensation & Canned Cycles)")
            lines.append("G54 (Workpiece Coordinate Offset)")
        elif self.controller == "GRBL":
            lines.append("G21 (Metric)")
            lines.append("G90 (Absolute)")
            lines.append("G17 (XY Plane)")
            lines.append("G54 (WCS G54)")
        else:  # LinuxCNC default
            lines.append("G21 (Metric)")
            lines.append("G90 (Absolute)")
            lines.append("G17 (XY Plane)")
            lines.append("G64 P0.05 (Continuous Path Mode with Tolerance)")
            lines.append("G54 (Workpiece Coordinate Offset)")

        lines.append("")

        current_tool_num = -1

        for op in operations:
            op_name = op.get("name", "Operation")
            tool = op.get("tool", {})
            t_num = tool.get("tool_number", 1)
            t_name = tool.get("name", "Tool")
            rpm = tool.get("spindle_rpm", 6000)
            feed = tool.get("feed_rate_mm_min", 800.0)
            plunge = tool.get("plunge_rate_mm_min", 250.0)
            waypoints = op.get("waypoints", [])

            lines.append(f"(--- OPERATION: {op_name} ---)")

            # Tool change if needed
            if t_num != current_tool_num:
                if self.controller != "GRBL":
                    lines.append(f"M5 (Spindle Stop)")
                    lines.append(f"T{t_num} M6 ({t_name})")
                else:
                    lines.append(f"(Tool Change T{t_num}: {t_name})")
                lines.append(f"S{rpm} M3 (Spindle CW)")
                lines.append(f"G4 P1.5 (Dwell for Spindle Acceleration)")
                if self.controller != "GRBL":
                    lines.append("M8 (Flood Coolant ON)")
                current_tool_num = t_num

            # Safe initial clearance
            lines.append("G0 Z15.000")

            last_mode = None
            last_feed = None

            for wp in waypoints:
                mtype, x, y, z = wp
                x_str = f"X{x:.3f}"
                y_str = f"Y{y:.3f}"
                z_str = f"Z{z:.3f}"

                if mtype == "RAPID":
                    lines.append(f"G0 {x_str} {y_str} {z_str}")
                    last_mode = "G0"
                elif mtype == "PLUNGE":
                    lines.append(f"G1 {z_str} F{plunge:.1f}")
                    last_mode = "G1"
                    last_feed = plunge
                else:  # FEED
                    feed_cmd = f" F{feed:.1f}" if last_feed != feed else ""
                    lines.append(f"G1 {x_str} {y_str} {z_str}{feed_cmd}")
                    last_mode = "G1"
                    last_feed = feed

            lines.append("G0 Z15.000 (Retract to Clearance)")
            lines.append("")

        # Postamble
        lines.append("(--- END OF PROGRAM ---)")
        lines.append("M5 (Spindle OFF)")
        if self.controller != "GRBL":
            lines.append("M9 (Coolant OFF)")
        lines.append("G0 Z30.000 (Safe Park Height)")
        lines.append("G0 X0.000 Y50.000 (Park Table for Unloading)")
        lines.append("M30 (End Program and Rewind)")
        lines.append("%")

        return "\n".join(lines)
