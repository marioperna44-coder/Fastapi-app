import io
import base64
import barcode
from barcode.writer import ImageWriter

def generate_barcode_base64(code: str) -> str:
    """Erstellt ein Barcode-Bild (Code128) ohne Text darunter und gibt es als Base64 zurück"""
    barcode_class = barcode.get_barcode_class("code128")
    rv = io.BytesIO()

    # Einstellungen für sauberes, randloses Bild
    options = {
        "write_text": False,   # ❌ keine Zahlen unter dem Strichcode
        "quiet_zone": 2,       # etwas weniger Rand
        "module_height": 15.0, # Strichhöhe anpassen
        "module_width": 0.3,   # Strichdicke
    }

    barcode_class(code, writer=ImageWriter()).write(rv, options)
    return base64.b64encode(rv.getvalue()).decode("utf-8")