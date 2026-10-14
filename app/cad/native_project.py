"""
Native FreeCAD Project (.FCStd) Manager
Saves and reloads complete parametric construction history, parameters, and metadata.
"""

import os
import json
from typing import Dict, Any

class NativeProjectManager:
    @staticmethod
    def save_project(doc_manager, filepath: str, parameters: Dict[str, Any] = None) -> str:
        """
        Saves document as native .FCStd and attaches design parameters sidecar metadata.
        """
        abs_path = os.path.abspath(filepath)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        doc = doc_manager.get_document()
        doc_manager.recompute()
        doc.saveAs(abs_path)

        if parameters:
            meta_path = abs_path + ".params.json"
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(parameters, f, indent=2)

        return abs_path
