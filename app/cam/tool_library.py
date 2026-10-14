"""
CNC Cutting Tool Library
Defines standard endmills, slot cutters, and drills with feeds, speeds, and dimensions.
"""

from typing import Dict, Any, List

class Tool:
    def __init__(
        self,
        tool_number: int,
        name: str,
        tool_type: str,  # FlatEndmill, BallEndmill, Drill, ChamferMill
        diameter_mm: float,
        flute_length_mm: float,
        overall_length_mm: float,
        flutes: int = 2,
        spindle_rpm: int = 8000,
        feed_rate_mm_min: float = 800.0,
        plunge_rate_mm_min: float = 250.0,
        max_stepdown_mm: float = 2.0
    ):
        self.tool_number = tool_number
        self.name = name
        self.tool_type = tool_type
        self.diameter = float(diameter_mm)
        self.flute_length = float(flute_length_mm)
        self.overall_length = float(overall_length_mm)
        self.flutes = flutes
        self.spindle_rpm = spindle_rpm
        self.feed_rate = float(feed_rate_mm_min)
        self.plunge_rate = float(plunge_rate_mm_min)
        self.max_stepdown = float(max_stepdown_mm)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_number": self.tool_number,
            "name": self.name,
            "type": self.tool_type,
            "diameter_mm": self.diameter,
            "flute_length_mm": self.flute_length,
            "spindle_rpm": self.spindle_rpm,
            "feed_rate_mm_min": self.feed_rate,
            "plunge_rate_mm_min": self.plunge_rate,
            "max_stepdown_mm": self.max_stepdown
        }


class ToolLibrary:
    def __init__(self):
        self.tools: Dict[int, Tool] = {}
        self._load_standard_tools()

    def _load_standard_tools(self):
        # T1: 10mm Roughing Endmill
        self.add_tool(Tool(1, "10mm Flat Endmill", "FlatEndmill", 10.0, 30.0, 75.0, 3, 6000, 1200.0, 300.0, 3.0))
        # T2: 6mm Finishing Endmill
        self.add_tool(Tool(2, "6mm Flat Endmill", "FlatEndmill", 6.0, 20.0, 60.0, 4, 8000, 900.0, 200.0, 1.5))
        # T3: 10mm Twist Drill
        self.add_tool(Tool(3, "10mm Twist Drill", "Drill", 10.0, 45.0, 85.0, 2, 2500, 350.0, 350.0, 10.0))
        # T4: 5mm Twist Drill
        self.add_tool(Tool(4, "5mm Twist Drill", "Drill", 5.0, 35.0, 70.0, 2, 4000, 400.0, 400.0, 5.0))
        # T5: 50mm Face Mill
        self.add_tool(Tool(5, "50mm Face Mill", "FlatEndmill", 50.0, 12.0, 90.0, 4, 3000, 1500.0, 200.0, 1.0))

    def add_tool(self, tool: Tool):
        self.tools[tool.tool_number] = tool

    def get_tool(self, tool_number: int) -> Tool:
        return self.tools.get(tool_number)

    def select_drill_for_hole(self, hole_dia_mm: float) -> Tool:
        """Finds closest matching drill or returns endmill for helical boring."""
        for t in self.tools.values():
            if t.tool_type == "Drill" and abs(t.diameter - hole_dia_mm) < 0.2:
                return t
        # Return 6mm endmill for helical pocketing if no exact drill
        return self.tools.get(2) or list(self.tools.values())[0]
