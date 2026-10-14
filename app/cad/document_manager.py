"""
CAD Document Manager
Provides FreeCAD document lifecycle, transaction management, and recomputation.
"""

import os
import sys

# Ensure FreeCAD bin and lib paths are present in sys.path
FREECAD_BIN = r"C:\Program Files\FreeCAD 1.1\bin"
FREECAD_LIB = r"C:\Program Files\FreeCAD 1.1\lib"
FREECAD_MOD = r"C:\Program Files\FreeCAD 1.1\Mod"

for p in [FREECAD_BIN, FREECAD_LIB, FREECAD_MOD]:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

try:
    import FreeCAD as App
    import Part
    import Sketcher
except ImportError as err:
    App = None
    Part = None
    Sketcher = None
    print(f"[Warning] Native FreeCAD imports not directly available: {err}")


class DocumentManager:
    def __init__(self, doc_name: str = "ParametricModel"):
        self.doc_name = doc_name
        self.doc = None
        self._init_doc()

    def _init_doc(self):
        if App is None:
            raise RuntimeError("FreeCAD module is not available in current Python environment.")
        # Close existing document with same name if open
        try:
            if App.getDocument(self.doc_name) is not None:
                App.closeDocument(self.doc_name)
        except Exception:
            pass
        self.doc = App.newDocument(self.doc_name)

    def get_document(self):
        return self.doc

    def recompute(self) -> bool:
        """Recomputes document and returns True if all features are valid."""
        if not self.doc:
            return False
        try:
            self.doc.recompute()
            for obj in self.doc.Objects:
                if hasattr(obj, "State") and "Failed" in obj.State:
                    return False
            return True
        except Exception as e:
            print(f"[DocumentManager] Recompute failed: {e}")
            return False

    def get_body(self, name: str = "Body"):
        """Finds or creates an App::Part / PartDesign::Body."""
        body = self.doc.getObject(name)
        if body is None:
            body = self.doc.addObject("PartDesign::Body", name)
        return body

    def save_fcstd(self, filepath: str) -> str:
        """Saves native FreeCAD project (.FCStd)."""
        abs_path = os.path.abspath(filepath)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        self.recompute()
        self.doc.saveAs(abs_path)
        return abs_path

    def close(self):
        if self.doc and App:
            try:
                App.closeDocument(self.doc_name)
            except Exception:
                pass
            self.doc = None
