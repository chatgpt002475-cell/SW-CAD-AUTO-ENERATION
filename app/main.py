"""
AI-Powered Image-to-3D Parametric CAD and CNC CAM Application
Main Orchestrator & CLI / GUI entrypoint.
"""

import os
import sys
import argparse
from typing import Dict, Any, Optional

# Ensure application root is in sys.path
APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

from app.image_processing import ImagePreprocessor, ScaleCalibrator, ContourDetector, CircleDetector
from app.reconstruction import FeatureRecognizer, FeaturePlanner, UncertaintyReporter
from app.reconstruction.classifier import MechanicalPartClassifier
from app.cad import DocumentManager, GeometryValidator, StepExporter, NativeProjectManager
from app.cad.stl_export import StlExporter
from app.cam import MachineConfig, ToolLibrary, MachiningSetup, OperationBuilder, ToolpathSimulator, GCodePostprocessor, GCodeValidator


class ImageToCadCamPipeline:
    def __init__(self, machine_controller: str = "LinuxCNC"):
        self.preprocessor = ImagePreprocessor()
        self.calibrator = ScaleCalibrator(units="mm")
        self.contour_detector = ContourDetector()
        self.circle_detector = CircleDetector()
        self.feature_recognizer = FeatureRecognizer(self.circle_detector, self.contour_detector)
        self.machine_config = MachineConfig(controller=machine_controller)
        self.tool_lib = ToolLibrary()

    def process_image_to_cad_and_cam(
        self,
        image_path: str,
        target_width_mm: float = 100.0,
        base_thickness_mm: float = 12.0,
        flange_height_mm: float = 0.0,
        output_step_path: Optional[str] = None,
        output_fcstd_path: Optional[str] = None,
        output_gcode_path: Optional[str] = None,
        output_stl_path: Optional[str] = None,
        user_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes end-to-end pipeline:
        Image -> Preprocessing -> Calibration -> Features -> CAD Solid -> Validation -> STEP -> STL -> CAM -> G-Code
        """
        classification = MechanicalPartClassifier.classify_and_calibrate(image_path)
        results = {
            "status": "pending",
            "image_path": image_path,
            "classification": classification,
            "calibration": None,
            "recognized_features": None,
            "uncertainty_report": None,
            "cad_validation": None,
            "step_export": None,
            "stl_export": None,
            "fcstd_project": None,
            "cam_simulation": None,
            "gcode_validation": None,
            "gcode_filepath": None
        }

        # 1. Image Preprocessing
        rgb_img = self.preprocessor.load_image(image_path)
        gray, binary_mask = self.preprocessor.preprocess(rgb_img)

        # 2. Contour Extraction
        parts = self.contour_detector.extract_hierarchy(binary_mask)
        if not parts:
            raise ValueError("No distinct part contours recognized in image.")

        primary_part = parts[0]
        bbox_px = primary_part["bbox_px"]
        width_px = float(bbox_px[2])

        # 3. Calibration
        self.calibrator.calibrate_by_known_dimension(width_px, target_width_mm, "mm")
        scale = self.calibrator.get_scale_factor()
        results["calibration"] = {
            "scale_mm_per_px": round(scale, 4),
            "target_width_mm": target_width_mm,
            "detected_width_px": width_px
        }

        # Center reference point
        cx_img = bbox_px[0] + bbox_px[2] / 2.0
        cy_img = bbox_px[1] + bbox_px[3] / 2.0

        # 4. Feature Recognition
        rec_features = self.feature_recognizer.recognize_features_from_part(
            primary_part, scale, (cx_img, cy_img), base_thickness_mm=base_thickness_mm
        )
        results["recognized_features"] = rec_features
        results["uncertainty_report"] = self.feature_recognizer.uncertainty.get_report()

        # Merge user params with auto-detected mechanical properties
        combined_params = user_params or {}
        combined_params.setdefault("category", classification.get("category", ""))
        combined_params.setdefault("target_width_mm", target_width_mm)
        combined_params.setdefault("target_height_mm", classification.get("target_height_mm", round(target_width_mm * 0.58, 1)))
        combined_params.setdefault("corner_fillet_radius_mm", classification.get("corner_fillet_radius_mm", 14.0))
        combined_params.setdefault("base_thickness_mm", base_thickness_mm)
        combined_params.setdefault("flange_height_mm", flange_height_mm)
        combined_params.setdefault("contour_points", classification.get("contour_points", []))
        combined_params.setdefault("detected_holes", classification.get("detected_holes", []))
        combined_params.setdefault("detected_slots", classification.get("detected_slots", []))
        combined_params.setdefault("detected_pockets", classification.get("detected_pockets", []))
        combined_params.setdefault("is_revolved", classification.get("is_revolved", False))

        # 5. Parametric CAD Reconstruction
        doc_mgr = DocumentManager("ReconstructedPart")
        planner = FeaturePlanner(doc_mgr)
        plan_res = planner.build_from_feature_tree(rec_features, combined_params)
        body = plan_res["body"]

        # 6. Solid Validation
        val = plan_res["validation"]
        results["cad_validation"] = val

        if not val["is_valid"]:
            results["status"] = "failed_validation"
            return results

        # 7. Native FCStd Project Saving
        if output_fcstd_path:
            fcstd_saved = NativeProjectManager.save_project(doc_mgr, output_fcstd_path, combined_params)
            results["fcstd_project"] = fcstd_saved

        # 8. STEP Export & Re-import Check
        if output_step_path:
            step_res = StepExporter.export_step(body, output_step_path)
            results["step_export"] = step_res

        # 8b. STL Export for Web 3D Viewport
        if output_stl_path:
            stl_res = StlExporter.export_stl(body, output_stl_path)
            results["stl_export"] = stl_res

        # 9. CNC CAM Setup & Operations
        bbox = val["bounding_box_mm"]
        cam_setup = MachiningSetup.from_solid_bbox(bbox, padding_xy_mm=5.0, padding_z_top_mm=1.0)
        op_builder = OperationBuilder(cam_setup, self.tool_lib)

        # A) Facing
        op_builder.add_facing_operation(cam_setup.stock_dims["x_mm"], cam_setup.stock_dims["y_mm"], depth_mm=1.0)
        # B) Drilling for recognized holes
        op_builder.add_drilling_operation(rec_features.get("holes", []))
        # C) Pocketing for recognized internal pockets
        op_builder.add_pocket_operation(rec_features.get("pockets", []))
        # D) 2D Profiling for outer perimeter
        base_pts = rec_features["base_feature"].get("points_mm", [])
        op_builder.add_profile_operation(base_pts, total_depth_mm=base_thickness_mm)

        # 10. Toolpath Simulation & Estimation
        sim_res = ToolpathSimulator.simulate(op_builder.operations, rapid_rate_mm_min=self.machine_config.rapid_rate)
        results["cam_simulation"] = sim_res

        # 11. G-Code Postprocessing
        post = GCodePostprocessor(controller=self.machine_config.controller)
        gcode_text = post.postprocess(op_builder.operations, program_name="RECONSTRUCTED_PART")

        # 12. G-Code Safety Validation
        gcode_val = GCodeValidator.validate(gcode_text, self.machine_config)
        results["gcode_validation"] = gcode_val

        if output_gcode_path:
            abs_gcode = os.path.abspath(output_gcode_path)
            os.makedirs(os.path.dirname(abs_gcode), exist_ok=True)
            with open(abs_gcode, "w", encoding="utf-8") as f:
                f.write(gcode_text)
            results["gcode_filepath"] = abs_gcode

        results["status"] = "success" if gcode_val["is_valid"] else "warning"
        return results


def main():
    parser = argparse.ArgumentParser(description="AI Image-to-Parametric-CAD & CNC CAM Generator")
    parser.add_argument("image", help="Path to input 2D image or drawing")
    parser.add_argument("-w", "--width", type=float, default=100.0, help="Target physical width in mm")
    parser.add_argument("-t", "--thickness", type=float, default=12.0, help="Base thickness in mm")
    parser.add_argument("--flange-height", type=float, default=0.0, help="Upright flange height in mm")
    parser.add_argument("-s", "--step", default="output_model.step", help="Output STEP filepath")
    parser.add_argument("-p", "--project", default="output_model.FCStd", help="Output native FreeCAD project (.FCStd)")
    parser.add_argument("-g", "--gcode", default="output_toolpath.nc", help="Output G-code filepath")
    parser.add_argument("-c", "--controller", default="LinuxCNC", choices=["LinuxCNC", "GRBL", "Fanuc", "Haas"], help="CNC Controller dialect")

    args = parser.parse_args()

    print(f"[*] Initializing CAD/CAM Pipeline for: {args.image}")
    pipeline = ImageToCadCamPipeline(machine_controller=args.controller)

    res = pipeline.process_image_to_cad_and_cam(
        image_path=args.image,
        target_width_mm=args.width,
        base_thickness_mm=args.thickness,
        flange_height_mm=args.flange_height,
        output_step_path=args.step,
        output_fcstd_path=args.project,
        output_gcode_path=args.gcode
    )

    print("\n--- PIPELINE EXECUTION SUMMARY ---")
    print(f"Status:             {res['status'].upper()}")
    print(f"Calibration Scale:  {res['calibration']['scale_mm_per_px']} mm/px")
    print(f"Solid Valid:        {res['cad_validation']['is_valid']}")
    print(f"Solid Volume:       {res['cad_validation']['volume_cm3']} cm³")
    if res['step_export']:
        print(f"STEP File:          {res['step_export']['filepath']} ({res['step_export']['filesize_bytes']} bytes)")
        print(f"STEP Re-import OK:  {res['step_export']['reimport_verified']}")
    if res['fcstd_project']:
        print(f"FCStd Project:      {res['fcstd_project']}")
    if res['cam_simulation']:
        print(f"Est. Cycle Time:    {res['cam_simulation']['estimated_cycle_time_formatted']}")
    if res['gcode_filepath']:
        print(f"G-Code File:        {res['gcode_filepath']}")
        print(f"G-Code Validated:   {res['gcode_validation']['is_valid']}")


if __name__ == "__main__":
    main()
