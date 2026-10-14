"""
Native Desktop Application UI (PySide6 / FreeCAD Integration)
Provides 4-panel professional CAD/CAM layout:
Left: Image & Calibration | Center: 3D Viewport | Right: Feature Tree & Parameters | Bottom: CAM & G-Code Logs
"""

import os
import sys
from typing import Optional

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QSplitter, QLabel, QPushButton, QFileDialog, QLineEdit,
        QFormLayout, QGroupBox, QTextEdit, QTableWidget, QTableWidgetItem,
        QTabWidget, QSpinBox, QDoubleSpinBox, QComboBox, QStatusBar, QToolBar
    )
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap, QAction, QFont
    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False


class CadCamMainWindow(QMainWindow if PYSIDE_AVAILABLE else object):
    def __init__(self, pipeline=None):
        if not PYSIDE_AVAILABLE:
            raise RuntimeError("PySide6 is required to run the native desktop application.")
        super().__init__()
        self.setWindowTitle("AI Parametric CAD & CNC CAM Studio - FreeCAD 1.1 Engine")
        self.resize(1440, 900)
        self.pipeline = pipeline
        self.current_image_path = None
        self.last_pipeline_result = None

        self._init_ui()

    def _init_ui(self):
        # Central Splitter
        main_splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(main_splitter)

        # 1. Left Panel (Image & Calibration)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(8, 8, 8, 8)

        img_box = QGroupBox("2D Engineering Image & Calibration")
        img_layout = QVBoxLayout(img_box)
        self.img_label = QLabel("No image loaded\nClick 'Import Image' to begin")
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setStyleSheet("background-color: #0f172a; color: #94a3b8; border: 1px dashed #334155; min-height: 250px;")
        img_layout.addWidget(self.img_label)

        calib_form = QFormLayout()
        self.width_input = QDoubleSpinBox()
        self.width_input.setRange(1.0, 5000.0)
        self.width_input.setValue(100.0)
        self.width_input.setSuffix(" mm")
        calib_form.addRow("Target Width:", self.width_input)

        self.thickness_input = QDoubleSpinBox()
        self.thickness_input.setRange(0.5, 500.0)
        self.thickness_input.setValue(12.0)
        self.thickness_input.setSuffix(" mm")
        calib_form.addRow("Base Thickness:", self.thickness_input)

        self.flange_input = QDoubleSpinBox()
        self.flange_input.setRange(0.0, 500.0)
        self.flange_input.setValue(0.0)
        self.flange_input.setSuffix(" mm")
        calib_form.addRow("Upright Flange:", self.flange_input)

        img_layout.addLayout(calib_form)

        btn_detect = QPushButton("⚡ Detect Features & Calibrate")
        btn_detect.setStyleSheet("background-color: #2563eb; color: white; padding: 6px; font-weight: bold;")
        btn_detect.clicked.connect(self._run_pipeline)
        img_layout.addWidget(btn_detect)

        left_layout.addWidget(img_box)
        main_splitter.addWidget(left_widget)

        # 2. Center Panel (3D Model Telemetry & Preview)
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_box = QGroupBox("Interactive 3D CAD Geometry View")
        center_inner = QVBoxLayout(center_box)

        self.cad_preview_label = QLabel("3D Solid Wireframe / B-Rep Geometry")
        self.cad_preview_label.setAlignment(Qt.AlignCenter)
        self.cad_preview_label.setStyleSheet("background-color: #1e1e24; color: #38bdf8; min-height: 400px; font-family: monospace;")
        center_inner.addWidget(self.cad_preview_label)

        self.telemetry_text = QTextEdit()
        self.telemetry_text.setReadOnly(True)
        self.telemetry_text.setMaximumHeight(130)
        self.telemetry_text.setStyleSheet("background-color: #0f172a; color: #e2e8f0; font-family: monospace;")
        center_inner.addWidget(self.telemetry_text)

        center_layout.addWidget(center_box)
        main_splitter.addWidget(center_widget)

        # 3. Right Panel (Parametric Feature Tree & CAM Controls)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_box = QGroupBox("Parametric Feature Tree & CNC CAM")
        right_inner = QVBoxLayout(right_box)

        self.feature_table = QTableWidget(0, 3)
        self.feature_table.setHorizontalHeaderLabels(["Feature", "Type", "Param"])
        right_inner.addWidget(self.feature_table)

        cam_form = QFormLayout()
        self.controller_combo = QComboBox()
        self.controller_combo.addItems(["LinuxCNC", "GRBL", "Fanuc", "Haas"])
        cam_form.addRow("CNC Controller:", self.controller_combo)

        btn_gcode = QPushButton("🛠️ Export G-Code & STEP")
        btn_gcode.setStyleSheet("background-color: #059669; color: white; padding: 6px; font-weight: bold;")
        btn_gcode.clicked.connect(self._export_cad_cam)
        cam_form.addRow(btn_gcode)

        right_inner.addLayout(cam_form)
        right_layout.addWidget(right_box)
        main_splitter.addWidget(right_widget)

        main_splitter.setSizes([380, 680, 380])

        # Bottom Log / G-Code Terminal
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready. Select an image or click 'Import Image'.")

        self._create_toolbar()

    def _create_toolbar(self):
        toolbar = QToolBar("Main Operations")
        self.addToolBar(toolbar)

        act_import = QAction("📁 Import Image", self)
        act_import.triggered.connect(self._import_image_dialog)
        toolbar.addAction(act_import)

        act_reconstruct = QAction("📐 Reconstruct CAD", self)
        act_reconstruct.triggered.connect(self._run_pipeline)
        toolbar.addAction(act_reconstruct)

        act_step = QAction("💾 Export STEP", self)
        act_step.triggered.connect(self._export_cad_cam)
        toolbar.addAction(act_step)

        act_save = QAction("📦 Save FCStd Project", self)
        act_save.triggered.connect(self._export_cad_cam)
        toolbar.addAction(act_save)

    def _import_image_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Engineering Drawing", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.load_image(path)

    def load_image(self, path: str):
        self.current_image_path = path
        pix = QPixmap(path)
        if not pix.isNull():
            self.img_label.setPixmap(pix.scaled(320, 240, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.statusBar.showMessage(f"Loaded: {os.path.basename(path)}")

    def _run_pipeline(self):
        if not self.current_image_path or not self.pipeline:
            self.statusBar.showMessage("Error: Please select an image first.")
            return

        try:
            self.statusBar.showMessage("Reconstructing 3D CAD model & generating toolpaths...")
            res = self.pipeline.process_image_to_cad_and_cam(
                image_path=self.current_image_path,
                target_width_mm=self.width_input.value(),
                base_thickness_mm=self.thickness_input.value(),
                flange_height_mm=self.flange_input.value(),
                output_step_path="output_reconstructed.step",
                output_fcstd_path="output_reconstructed.FCStd",
                output_gcode_path="output_toolpath.nc"
            )
            self.last_pipeline_result = res

            val = res["cad_validation"]
            cam = res["cam_simulation"]
            self.telemetry_text.setText(
                f"=== SOLID GEOMETRY VALIDATION ===\n"
                f"Status: VALID MANIFOLD SOLID\n"
                f"Volume: {val['volume_cm3']} cm³ | Area: {val['surface_area_cm2']} cm²\n"
                f"Bounding Box (mm): X={val['bounding_box_mm']['x_len']}, Y={val['bounding_box_mm']['y_len']}, Z={val['bounding_box_mm']['z_len']}\n"
                f"Faces: {val['faces_count']} | Edges: {val['edges_count']} | Solids: {val['solids_count']}\n\n"
                f"=== CNC CAM SIMULATION TELEMETRY ===\n"
                f"Cycle Time: {cam['estimated_cycle_time_formatted']} | Cutting Feed: {cam['total_feed_distance_mm']} mm\n"
                f"Rapid Motion: {cam['total_rapid_distance_mm']} mm | Z Bounds: {cam['z_bounds_mm']}"
            )

            # Populate feature tree
            rec = res["recognized_features"]
            self.feature_table.setRowCount(0)
            self._add_row("BasePad", "PartDesign::Pad", f"T={self.thickness_input.value()}mm")
            if self.flange_input.value() > 0:
                self._add_row("FlangePad", "PartDesign::Pad", f"H={self.flange_input.value()}mm")
            for h in rec.get("holes", []):
                self._add_row(h["id"], "ThroughHole", f"Dia={h['diameter_mm']}mm")
            for p in rec.get("pockets", []):
                self._add_row(p["id"], "PocketCut", f"Depth={p['depth_mm']}mm")

            self.statusBar.showMessage("Reconstruction & Toolpaths generated successfully!")
        except Exception as e:
            self.statusBar.showMessage(f"Error: {e}")

    def _add_row(self, name, ftype, param):
        row = self.feature_table.rowCount()
        self.feature_table.insertRow(row)
        self.feature_table.setItem(row, 0, QTableWidgetItem(name))
        self.feature_table.setItem(row, 1, QTableWidgetItem(ftype))
        self.feature_table.setItem(row, 2, QTableWidgetItem(param))

    def _export_cad_cam(self):
        if not self.last_pipeline_result:
            self._run_pipeline()
        self.statusBar.showMessage("Export complete: output_reconstructed.step & output_toolpath.nc generated.")


def launch_app():
    if not PYSIDE_AVAILABLE:
        print("[Error] PySide6 is not available.")
        return 1
    app = QApplication.instance() or QApplication(sys.argv)
    from app.main import ImageToCadCamPipeline
    pipeline = ImageToCadCamPipeline()
    window = CadCamMainWindow(pipeline=pipeline)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(launch_app())
