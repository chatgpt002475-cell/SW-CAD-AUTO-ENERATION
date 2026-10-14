"""
CNC Machining Operation Builder
Constructs 3D toolpaths: Facing, Pocketing, Drilling, and 2D Profiling.
"""

from typing import List, Dict, Any, Tuple
from .tool_library import Tool, ToolLibrary
from .setup_builder import MachiningSetup


class OperationBuilder:
    def __init__(self, setup: MachiningSetup, tool_lib: ToolLibrary):
        self.setup = setup
        self.tool_lib = tool_lib
        self.operations: List[Dict[str, Any]] = []

    def add_facing_operation(self, stock_x: float, stock_y: float, depth_mm: float = 1.0, tool_num: int = 5) -> Dict[str, Any]:
        """Creates face milling raster path across stock top."""
        tool = self.tool_lib.get_tool(tool_num) or self.tool_lib.get_tool(1)
        stepover = tool.diameter * 0.7
        half_x = stock_x / 2.0 + 5.0
        half_y = stock_y / 2.0 + 5.0

        waypoints = []
        y = -half_y
        direction = 1
        while y <= half_y:
            x_start = -half_x if direction == 1 else half_x
            x_end = half_x if direction == 1 else -half_x
            waypoints.append(("RAPID", x_start, y, 5.0))
            waypoints.append(("FEED", x_start, y, 0.0))
            waypoints.append(("FEED", x_end, y, 0.0))
            waypoints.append(("RAPID", x_end, y, 5.0))
            y += stepover
            direction *= -1

        op = {
            "name": "Op1_Facing",
            "type": "Facing",
            "tool": tool.to_dict(),
            "target_z_mm": 0.0,
            "waypoints": waypoints
        }
        self.operations.append(op)
        return op

    def add_drilling_operation(self, holes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Creates canned drilling cycles for recognized through-holes."""
        if not holes:
            return None

        # Select tool based on first hole diameter
        sample_dia = holes[0].get("diameter_mm", 10.0)
        tool = self.tool_lib.select_drill_for_hole(sample_dia)

        waypoints = []
        for h in holes:
            cx = float(h.get("center_x_mm", 0.0))
            cy = float(h.get("center_y_mm", 0.0))
            depth = float(h.get("depth_mm", 12.0))

            waypoints.append(("RAPID", cx, cy, 5.0))
            # Peck drilling (2mm pecks)
            curr_z = 0.0
            target_z = -depth - 1.5  # Break-through allowance
            while curr_z > target_z:
                curr_z = max(target_z, curr_z - 3.0)
                waypoints.append(("FEED", cx, cy, curr_z))
                waypoints.append(("RAPID", cx, cy, 1.0))
                waypoints.append(("RAPID", cx, cy, curr_z + 0.5))

            waypoints.append(("RAPID", cx, cy, 15.0))  # Retract

        op = {
            "name": "Op2_Drilling",
            "type": "Drilling",
            "tool": tool.to_dict(),
            "holes_count": len(holes),
            "waypoints": waypoints
        }
        self.operations.append(op)
        return op

    def add_pocket_operation(self, pockets: List[Dict[str, Any]], tool_num: int = 2) -> Dict[str, Any]:
        """Creates pocket roughing toolpath for internal cavities."""
        if not pockets:
            return None

        tool = self.tool_lib.get_tool(tool_num) or self.tool_lib.get_tool(1)
        waypoints = []

        for p in pockets:
            pts = p.get("points_mm", [])
            depth = float(p.get("depth_mm", 4.0))
            if len(pts) < 3:
                continue

            stepdown = tool.max_stepdown
            curr_z = 0.0
            while curr_z > -depth:
                curr_z = max(-depth, curr_z - stepdown)
                # Rapid to start
                waypoints.append(("RAPID", pts[0][0], pts[0][1], 5.0))
                waypoints.append(("PLUNGE", pts[0][0], pts[0][1], curr_z))
                # Contour perimeter of pocket
                for pt in pts[1:]:
                    waypoints.append(("FEED", pt[0], pt[1], curr_z))
                waypoints.append(("FEED", pts[0][0], pts[0][1], curr_z))
                waypoints.append(("RAPID", pts[0][0], pts[0][1], 5.0))

        op = {
            "name": "Op3_PocketMilling",
            "type": "Pocketing",
            "tool": tool.to_dict(),
            "waypoints": waypoints
        }
        self.operations.append(op)
        return op

    def add_profile_operation(self, perimeter_pts: List[Tuple[float, float]], total_depth_mm: float, tool_num: int = 1) -> Dict[str, Any]:
        """Creates 2D perimeter contouring profile passes with stepdowns."""
        if len(perimeter_pts) < 3:
            return None

        tool = self.tool_lib.get_tool(tool_num)
        stepdown = tool.max_stepdown
        waypoints = []

        curr_z = 0.0
        while curr_z > -total_depth_mm:
            curr_z = max(-total_depth_mm, curr_z - stepdown)
            # Rapid to entry point
            waypoints.append(("RAPID", perimeter_pts[0][0], perimeter_pts[0][1], 5.0))
            waypoints.append(("PLUNGE", perimeter_pts[0][0], perimeter_pts[0][1], curr_z))
            # Contour
            for pt in perimeter_pts[1:]:
                waypoints.append(("FEED", pt[0], pt[1], curr_z))
            waypoints.append(("FEED", perimeter_pts[0][0], perimeter_pts[0][1], curr_z))
            waypoints.append(("RAPID", perimeter_pts[0][0], perimeter_pts[0][1], 15.0))

        op = {
            "name": "Op4_2DProfiling",
            "type": "Profiling",
            "tool": tool.to_dict(),
            "target_depth_mm": total_depth_mm,
            "waypoints": waypoints
        }
        self.operations.append(op)
        return op
