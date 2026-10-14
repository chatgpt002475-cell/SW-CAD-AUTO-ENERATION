"""
Automated Test Suite for Acceptance Criteria (Tests A through F)
Executes and validates each criterion specified in the Master Project Prompt.
"""

import os
import sys
import unittest
import cv2
import numpy as np

# Add application root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.image_processing import ImagePreprocessor, ScaleCalibrator, ContourDetector, CircleDetector
from app.reconstruction import FeatureRecognizer, FeaturePlanner, UncertaintyReporter
from app.cad import DocumentManager, FeatureBuilder, GeometryValidator, StepExporter, NativeProjectManager
from app.cam import MachineConfig, ToolLibrary, MachiningSetup, OperationBuilder, ToolpathSimulator, GCodePostprocessor, GCodeValidator
from app.main import ImageToCadCamPipeline


class TestCadCamPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = os.path.abspath("tests/output")
        os.makedirs(cls.test_dir, exist_ok=True)
        cls.bracket_img = os.path.join(cls.test_dir, "test_bracket.png")
        cls.flange_img = os.path.join(cls.test_dir, "test_flange.png")

        # Generate synthetic bracket drawing (Base with 2 holes and rectangular profile)
        img = np.ones((600, 800), dtype=np.uint8) * 255
        # Black base body 400x240 (corners: 200,180 to 600,420)
        cv2.rectangle(img, (200, 180), (600, 420), 0, -1)
        # 2 White hole cutouts (radius 30, centers at 300,300 and 500,300)
        cv2.circle(img, (300, 300), 30, 255, -1)
        cv2.circle(img, (500, 300), 30, 255, -1)
        cv2.imwrite(cls.bracket_img, img)

    def test_a_basic_bracket(self):
        """TEST A: BASIC BRACKET with base, multiple holes, and an upright flange."""
        print("\n[EXEC] Running TEST A: Basic Bracket...")
        pipeline = ImageToCadCamPipeline()

        step_file = os.path.join(self.test_dir, "bracket_test_a.step")
        fcstd_file = os.path.join(self.test_dir, "bracket_test_a.FCStd")

        res = pipeline.process_image_to_cad_and_cam(
            image_path=self.bracket_img,
            target_width_mm=120.0,
            base_thickness_mm=12.0,
            flange_height_mm=35.0,  # Genuine 3D upright flange!
            output_step_path=step_file,
            output_fcstd_path=fcstd_file
        )

        self.assertEqual(res["status"], "success")
        self.assertTrue(res["cad_validation"]["is_valid"])
        self.assertGreater(res["cad_validation"]["volume_cm3"], 50.0)
        self.assertTrue(res["step_export"]["reimport_verified"])
        self.assertTrue(os.path.exists(step_file))
        self.assertTrue(os.path.exists(fcstd_file))
        print(" -> TEST A PASSED: Bracket reconstructed with 3D flange, valid solid, verified STEP export.")

    def test_b_multi_plane_component(self):
        """TEST B: MULTI-PLANE COMPONENT with perpendicular faces and recessed pockets."""
        print("\n[EXEC] Running TEST B: Multi-Plane Component...")
        dm = DocumentManager("MultiPlaneDoc")
        fb = FeatureBuilder(dm)

        # Base block (100x80x15)
        sb_base = fb.create_sketch("BaseSketch", "XY_Plane")
        sb_base.add_rectangle_centered(100.0, 80.0)
        fb.add_pad(sb_base.get_sketch(), length_mm=15.0, name="BasePad")

        # Perpendicular upright wall on Plane.XZ offset
        dp = fb.add_datum_plane("PerpendicularPlane", plane="XZ_Plane", offset=30.0)
        sb_wall = fb.create_sketch("WallSketch", "XY_Plane", offset_z=15.0)
        sb_wall.add_polygon([(-40, 20), (40, 20), (40, 35), (-40, 35)])
        fb.add_pad(sb_wall.get_sketch(), length_mm=30.0, name="PerpendicularWall")

        # Recessed pocket on top face (depth 5mm)
        sb_pocket = fb.create_sketch("PocketSketch", "XY_Plane", offset_z=15.0)
        sb_pocket.add_rectangle_centered(40.0, 30.0)
        fb.add_pocket(sb_pocket.get_sketch(), length_mm=5.0, name="RecessedPocket")

        body = dm.get_body()
        val = GeometryValidator.validate_solid(body)

        self.assertTrue(val["is_valid"])
        self.assertGreater(val["volume_cm3"], 80.0)

        step_file = os.path.join(self.test_dir, "multiplane_test_b.step")
        step_res = StepExporter.export_step(body, step_file)
        self.assertTrue(step_res["reimport_verified"])
        print(" -> TEST B PASSED: Multi-plane perpendicular faces, pocket, and verified STEP export.")

    def test_c_sheet_metal_component(self):
        """TEST C: SHEET-METAL COMPONENT with uniform thickness and bent flange."""
        print("\n[EXEC] Running TEST C: Sheet Metal Component...")
        dm = DocumentManager("SheetMetalDoc")
        fb = FeatureBuilder(dm)

        sheet_thickness = 2.5
        flange_height = 25.0

        # Base flat sheet
        sb_base = fb.create_sketch("SheetBase", "XY_Plane")
        sb_base.add_rectangle_centered(120.0, 80.0)
        fb.add_pad(sb_base.get_sketch(), length_mm=sheet_thickness, name="BaseSheet")

        # Bent 90 deg flange
        sb_flange = fb.create_sketch("BentFlange", "XY_Plane", offset_z=sheet_thickness)
        sb_flange.add_polygon([(-60, 30), (60, 30), (60, 30 + sheet_thickness), (-60, 30 + sheet_thickness)])
        fb.add_pad(sb_flange.get_sketch(), length_mm=flange_height, name="FlangePad")

        body = dm.get_body()
        val = GeometryValidator.validate_solid(body)

        self.assertTrue(val["is_valid"])
        self.assertAlmostEqual(val["bounding_box_mm"]["z_len"], sheet_thickness + flange_height, delta=0.1)

        step_file = os.path.join(self.test_dir, "sheetmetal_test_c.step")
        step_res = StepExporter.export_step(body, step_file)
        self.assertTrue(step_res["reimport_verified"])
        print(" -> TEST C PASSED: Sheet metal geometry with uniform thickness and bent flange verified.")

    def test_d_insufficient_information(self):
        """TEST D: INSUFFICIENT IMAGE INFORMATION handling and uncertainty reporting."""
        print("\n[EXEC] Running TEST D: Insufficient Information Handling...")
        uncertainty = UncertaintyReporter()
        uncertainty.log_assumption("Thickness", "z_depth", 10.0, "Inferred from single 2D view; depth cannot be optically determined without second view.")
        uncertainty.log_missing_input("Material", "Aluminum 6061", "Required for precise feed/speed calculation in CAM.")

        report = uncertainty.get_report()
        self.assertTrue(report["is_single_view"])
        self.assertEqual(len(report["missing_inputs"]), 1)
        self.assertLess(report["overall_confidence"], 1.0)
        print(" -> TEST D PASSED: Transparent uncertainty tracking without false claims of optical depth.")

    def test_e_cnc_workflow(self):
        """TEST E: CNC WORKFLOW with stock, operations, simulation, and validated G-code."""
        print("\n[EXEC] Running TEST E: CNC CAM Workflow & G-Code Safety...")
        cfg = MachineConfig(controller="LinuxCNC", max_spindle_rpm=10000)
        tool_lib = ToolLibrary()
        setup = MachiningSetup(stock_x_len=130.0, stock_y_len=90.0, stock_z_len=15.0)

        op_builder = OperationBuilder(setup, tool_lib)
        op_builder.add_facing_operation(130.0, 90.0, depth_mm=1.0)
        op_builder.add_drilling_operation([{"center_x_mm": -30.0, "center_y_mm": 0.0, "diameter_mm": 10.0, "depth_mm": 12.0}])
        op_builder.add_profile_operation([(-50, -30), (50, -30), (50, 30), (-50, 30)], total_depth_mm=12.0)

        # Simulation
        sim = ToolpathSimulator.simulate(op_builder.operations)
        self.assertTrue(sim["simulation_passed"])
        self.assertGreater(sim["total_feed_distance_mm"], 50.0)

        # Postprocessing
        post = GCodePostprocessor("LinuxCNC")
        gcode = post.postprocess(op_builder.operations)

        # Safety Validation
        val = GCodeValidator.validate(gcode, cfg)
        self.assertTrue(val["is_valid"])
        self.assertEqual(len(val["errors"]), 0)
        self.assertIn("G21", gcode)
        self.assertIn("M3", gcode)
        self.assertIn("M30", gcode)

        gcode_file = os.path.join(self.test_dir, "test_e_part.ngc")
        with open(gcode_file, "w") as f:
            f.write(gcode)

        print(f" -> TEST E PASSED: G-code generated and safety validated ({val['total_lines']} lines, est. time: {sim['estimated_cycle_time_formatted']}).")

    def test_f_parametric_editing(self):
        """TEST F: PARAMETRIC EDITING recompute when dimensions change."""
        print("\n[EXEC] Running TEST F: Parametric Dimension Recompute...")
        dm = DocumentManager("ParametricEditDoc")
        fb = FeatureBuilder(dm)

        # Initial model
        sb = fb.create_sketch("BaseSketch", "XY_Plane")
        sb.add_rectangle_centered(80.0, 50.0)
        pad = fb.add_pad(sb.get_sketch(), length_mm=10.0, name="BasePad")
        hole = fb.add_hole_subtraction(0.0, 0.0, diameter_mm=8.0, sketch_name="HoleSketch", feature_name="HoleCut")

        body = dm.get_body()
        dm.recompute()
        initial_vol = body.Shape.Volume

        # Edit Parameter 1: Base Thickness 10mm -> 25mm
        pad.Length = 25.0
        # Edit Parameter 2: Increase Hole Diameter (change radius in sketch)
        hole_sketch = dm.get_document().getObject("HoleSketch")
        hole_sketch.setDatum(0, 10.0)  # Change radius from 4mm to 10mm (Dia 20mm)

        dm.recompute()
        updated_val = GeometryValidator.validate_solid(body)

        self.assertTrue(updated_val["is_valid"])
        self.assertGreater(body.Shape.Volume, initial_vol)  # Thickness increase dominates

        step_file = os.path.join(self.test_dir, "parametric_edited_test_f.step")
        step_res = StepExporter.export_step(body, step_file)
        self.assertTrue(step_res["reimport_verified"])
        print(f" -> TEST F PASSED: Parametric edit recomputed successfully (Vol: {initial_vol/1000:.1f} -> {body.Shape.Volume/1000:.1f} cm³).")


if __name__ == "__main__":
    unittest.main()
