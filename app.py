"""Start PROMARK LED STUDIO from the outer extracted folder: python app.py."""
from pathlib import Path
import runpy
import sys

project = Path(__file__).resolve().parent / "av_wall_designer"
sys.path.insert(0, str(project))
try:
    import flask
except ModuleNotFoundError:
    print("Flask is not installed. Run START-HERE.bat to set up and start PROMARK LED STUDIO.")
    print("Or run: python -m pip install -r requirements.txt")
    sys.exit(1)
runpy.run_path(str(project / "app.py"), run_name="__main__")
