import importlib.util
from pathlib import Path

controller_path = (
    Path(__file__).resolve().parents[1] / "src" / "controller.py"
)
spec = importlib.util.spec_from_file_location(
    "controller",
    controller_path,
)
controller_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller_module)

IncidentController = controller_module.IncidentController
