"""
AI-Powered Image-to-3D Parametric CAD & CNC CAM Web Studio Server
Runs on FreeCAD 1.1 + OpenCV engine in dedicated virtual environment.
"""

import os
import sys
import uuid
import json
from flask import Flask, request, jsonify, render_template, send_from_directory

# Ensure repository root is in sys.path
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from app.main import ImageToCadCamPipeline
from app.reconstruction.classifier import MechanicalPartClassifier

app = Flask(__name__, template_folder="templates", static_folder="static")

UPLOAD_FOLDER = os.path.join(REPO_ROOT, "workspace_data", "uploads")
OUTPUT_FOLDER = os.path.join(REPO_ROOT, "workspace_data", "outputs")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Shared pipeline instance
pipeline = ImageToCadCamPipeline(machine_controller="LinuxCNC")


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "service": "AI-Parametric-CAD-CAM-Studio",
        "engine": "FreeCAD 1.1.4 + OpenCASCADE 8.0 + OpenCV",
        "port": 9000,
        "commit": "b1e8e7d90fe0c5ae03b32e112e8a0fd1c1c9e7b5"
    })


@app.route("/api/status")
def status():
    return jsonify({
        "commit": "b1e8e7d",
        "repository": "https://github.com/chatgpt002475-cell/SW-CAD-AUTO-ENERATION.git",
        "python_runtime": sys.version,
        "freecad_version": "1.1.4",
        "supported_controllers": ["LinuxCNC", "GRBL", "Fanuc", "Haas"],
        "export_formats": ["STEP (ISO 10303 AP214)", "FreeCAD (.FCStd)", "G-Code (.nc)", "STL (.stl)"]
    })


@app.route("/api/analyze_image", methods=["POST"])
def analyze_image():
    """
    Fast image analysis endpoint:
    Classifies part category (Sheet Metal, Stamping, Shaft, Flange)
    and returns auto-calibrated target width, thickness, and flange height.
    """
    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files["image"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    job_id = str(uuid.uuid4())[:8]
    ext = os.path.splitext(file.filename)[1].lower() or ".png"
    safe_name = f"preview_{job_id}{ext}"
    input_path = os.path.join(UPLOAD_FOLDER, safe_name)
    file.save(input_path)

    try:
        ref_w = request.form.get("target_width_mm")
        ref_w_val = float(ref_w) if ref_w else None
        calib_data = MechanicalPartClassifier.classify_and_calibrate(input_path, reference_width_mm=ref_w_val)
        return jsonify({
            "status": "success",
            "job_id": job_id,
            "filename": safe_name,
            **calib_data
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/reconstruct", methods=["POST"])
def reconstruct():
    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files["image"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    job_id = str(uuid.uuid4())[:8]
    ext = os.path.splitext(file.filename)[1].lower() or ".png"
    safe_name = f"part_{job_id}{ext}"
    input_path = os.path.join(UPLOAD_FOLDER, safe_name)
    file.save(input_path)

    # Form parameters
    width_mm = float(request.form.get("target_width_mm") or request.form.get("target_width") or 100.0)
    thickness_mm = float(request.form.get("base_thickness_mm") or request.form.get("base_thickness") or 3.0)
    flange_h_mm = float(request.form.get("flange_height_mm") or request.form.get("flange_height") or 0.0)
    controller = request.form.get("controller", "LinuxCNC")

    step_name = f"cad_{job_id}.step"
    fcstd_name = f"cad_{job_id}.FCStd"
    gcode_name = f"cam_{job_id}.nc"
    stl_name = f"cad_{job_id}.stl"

    step_path = os.path.join(OUTPUT_FOLDER, step_name)
    fcstd_path = os.path.join(OUTPUT_FOLDER, fcstd_name)
    gcode_path = os.path.join(OUTPUT_FOLDER, gcode_name)
    stl_path = os.path.join(OUTPUT_FOLDER, stl_name)

    try:
        pipeline.machine_config.controller = controller
        results = pipeline.process_image_to_cad_and_cam(
            image_path=input_path,
            target_width_mm=width_mm,
            base_thickness_mm=thickness_mm,
            flange_height_mm=flange_h_mm,
            output_step_path=step_path,
            output_fcstd_path=fcstd_path,
            output_gcode_path=gcode_path,
            output_stl_path=stl_path
        )

        # Read G-code sample lines
        gcode_sample = ""
        if os.path.exists(gcode_path):
            with open(gcode_path, "r", encoding="utf-8") as gf:
                gcode_sample = gf.read()

        response_data = {
            "status": results["status"],
            "job_id": job_id,
            "classification": results.get("classification"),
            "calibration": results["calibration"],
            "recognized_features": results["recognized_features"],
            "uncertainty_report": results["uncertainty_report"],
            "cad_validation": results["cad_validation"],
            "cam_simulation": results["cam_simulation"],
            "gcode_validation": results["gcode_validation"],
            "gcode_text": gcode_sample,
            "downloads": {
                "step": f"/api/download/{step_name}",
                "fcstd": f"/api/download/{fcstd_name}",
                "gcode": f"/api/download/{gcode_name}",
                "stl": f"/api/download/{stl_name}"
            }
        }
        return jsonify(response_data)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/ai_command", methods=["POST"])
def ai_command():
    """
    Intelligent Search & Command Engine Endpoint:
    Parses natural language requests to modify parameters, change controllers,
    reconstruct models, or answer engineering queries.
    """
    data = request.get_json() or {}
    query = (data.get("query") or "").strip()
    if not query:
        return jsonify({"status": "error", "message": "Empty query"}), 400

    q_lower = query.lower()
    changes = {}
    actions = []

    # 1. Parameter extraction
    import re
    w_match = re.search(r'(?:width|w|target\s*width)\s*(?:to|=)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:mm)?', q_lower)
    if w_match:
        val = float(w_match.group(1))
        changes["target_width_mm"] = val
        actions.append(f"Set target width to {val} mm")

    t_match = re.search(r'(?:thickness|gauge|t|base\s*thickness)\s*(?:to|=)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:mm)?', q_lower)
    if t_match:
        val = float(t_match.group(1))
        changes["base_thickness_mm"] = val
        actions.append(f"Set base thickness to {val} mm")

    f_match = re.search(r'(?:flange|flange\s*height|fh)\s*(?:to|=)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:mm)?', q_lower)
    if f_match:
        val = float(f_match.group(1))
        changes["flange_height_mm"] = val
        actions.append(f"Set flange height to {val} mm")

    # 2. Controller Dialect
    if "fanuc" in q_lower:
        changes["controller"] = "Fanuc"
        actions.append("Switched CNC dialect to Fanuc")
    elif "haas" in q_lower:
        changes["controller"] = "Haas"
        actions.append("Switched CNC dialect to Haas")
    elif "grbl" in q_lower:
        changes["controller"] = "GRBL"
        actions.append("Switched CNC dialect to GRBL")
    elif "linuxcnc" in q_lower or "linux" in q_lower:
        changes["controller"] = "LinuxCNC"
        actions.append("Switched CNC dialect to LinuxCNC")

    # 3. Actions / View / Pipeline
    if any(k in q_lower for k in ["wireframe", "wire frame", "shaded"]):
        actions.append("toggle_wireframe")
    if any(k in q_lower for k in ["top view", "view top", "xy plane"]):
        actions.append("set_view_top")
    if any(k in q_lower for k in ["front view", "view front", "xz plane"]):
        actions.append("set_view_front")
    if any(k in q_lower for k in ["side view", "view side", "yz plane", "right view"]):
        actions.append("set_view_side")
    if any(k in q_lower for k in ["iso", "isometric", "reset view"]):
        actions.append("set_view_iso")
    if any(k in q_lower for k in ["reconstruct", "generate cad", "build 3d", "remaster"]):
        actions.append("run_reconstruction")

    # 4. Answers / Queries
    info = None
    if any(k in q_lower for k in ["volume", "dimensions", "area", "material", "specs"]):
        info = {
            "material": "6061-T6 Aerospace Aluminum (default) / AISI 304 Stainless",
            "cad_engine": "FreeCAD 1.1 + OpenCASCADE 8.0 B-Rep Kernel",
            "precision": "0.01 mm tolerance",
            "manufacturing_dialect": changes.get("controller", "LinuxCNC")
        }

    return jsonify({
        "status": "success",
        "query": query,
        "actions": actions,
        "changes": changes,
        "info": info,
        "message": "; ".join(actions) if actions else "Query parsed. Tool updated."
    })


@app.route("/api/download/<path:filename>", methods=["GET"])
def download_file(filename):
    clean_name = os.path.basename(filename)
    target_path = os.path.join(OUTPUT_FOLDER, clean_name)
    if not os.path.exists(target_path):
        return jsonify({"error": f"File '{clean_name}' not found"}), 404
    return send_from_directory(OUTPUT_FOLDER, clean_name, as_attachment=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 9000))
    print(f"===========================================================")
    print(f"  AI PARAMETRIC CAD & CNC CAM STUDIO")
    print(f"  Repository Commit: b1e8e7d")
    print(f"  Local Hosting: http://localhost:{port}")
    print(f"===========================================================")
    app.run(host="0.0.0.0", port=port, debug=False)
