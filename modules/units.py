# modules/units.py
CM_TO_PT = 28.3465
MM_TO_PT = CM_TO_PT / 10.0

def cm(v: float) -> float:
    return v * CM_TO_PT

def mm(v: float) -> float:
    return v * MM_TO_PT
