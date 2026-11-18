"""Load exactly the reviewed ORION JARVIS 0.8.0 backend source.

The source is stored as a deterministic gzip/base64 build artifact to
preserve the original reviewed ZIP bytes across deployment. A checksum
mismatch aborts startup. No network calls or AI activation occur here.
"""
import base64
import gzip
import hashlib
import importlib.util
import pathlib

PACKAGE = pathlib.Path(__file__).parent
EXPECTED_SHA256 = "a1493dffc548e815aca6b540daf7f2aab5d1fc0262c9f733daa0f87184951cd6"
encoded = (PACKAGE / "engine.py.gz.b64").read_text(encoding="ascii").strip()
source = gzip.decompress(base64.b64decode(encoded, validate=True))
actual_hash = hashlib.sha256(source).hexdigest()
if actual_hash != EXPECTED_SHA256:
    raise RuntimeError("JARVIS 0.8.0 engine checksum does not match the reviewed source")

engine_path = PACKAGE / "jarvis_engine_runtime.py"
engine_path.write_bytes(source)
spec = importlib.util.spec_from_file_location("jarvis_engine_runtime", engine_path)
if not spec or not spec.loader:
    raise RuntimeError("Unable to load reviewed JARVIS engine")
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
app = engine.app

from icloud_calendar import register as register_icloud_calendar
register_icloud_calendar(app, engine.user_context)
