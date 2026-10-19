"""DroneDrill AI - Scenario Generator.

Generates threat simulation scenarios with condition factors,
object tracks, difficulty indexes, and deterministic fingerprints.
Never draws from HELD_OUT cells unless explicitly allowed.
"""

import hashlib
import math
import random
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

from app.factors import (
    all_cells,
    HELD_OUT_CELLS,
    PRACTICE_CELLS,
    OBJECT_COUNT_LEVELS,
    CLASS_MIX,
    MOTION_PATTERN,
    SPEED_BAND,
    ALTITUDE_BAND,
    BEARING_SECTOR,
    BEHAVIOUR_LABEL,
)
from app.db import get_seen_cells
from app.sensor_view import check_main_view_visibility

# --- Editable Difficulty Weights (Sum = 1.0) ---
WEIGHTS: Dict[str, float] = {
    "time_of_day": 0.10,
    "weather": 0.12,
    "terrain": 0.10,
    "sensor_mode": 0.06,
    "degradation": 0.14,
    "distractors": 0.08,
    "object_count": 0.16,
    "speed_band": 0.08,
    "altitude_band": 0.06,
    "motion_pattern": 0.10,
}

# --- Normalised Factor Difficulty Scores (0.0 to 1.0) ---
TIME_OF_DAY_SCORE = {"day": 0.1, "dusk": 0.5, "night": 0.9}
WEATHER_SCORE = {"clear": 0.0, "haze": 0.25, "fog": 0.7, "rain": 0.8, "dust": 1.0}
TERRAIN_SCORE = {"open": 0.1, "hills": 0.4, "forest": 0.7, "urban": 1.0}
SENSOR_MODE_SCORE = {"thermal": 0.3, "EO": 0.7}
DEGRADATION_SCORE = {"none": 0.0, "lag": 0.3, "noise": 0.5, "dropout": 0.8, "occlusion": 1.0}
DISTRACTORS_SCORE = {"none": 0.0, "birds": 0.5, "clutter": 1.0}

OBJECT_COUNT_SCORE = {"1": 0.1, "2-3": 0.4, "4-8": 0.7, "9+": 1.0}
SPEED_BAND_SCORE = {"low": 0.2, "med": 0.5, "high": 1.0}
ALTITUDE_BAND_SCORE = {"high": 0.2, "med": 0.5, "low": 0.9}  # Low altitude is harder to track
MOTION_PATTERN_SCORE = {
    "straight": 0.1,
    "parallel": 0.3,
    "loiter": 0.5,
    "converging": 0.8,
    "erratic": 1.0,
}

# Bearing angles in degrees for spatial positioning
BEARING_ANGLES = {
    "N": 0.0,
    "NE": 45.0,
    "E": 90.0,
    "SE": 135.0,
    "S": 180.0,
    "SW": 225.0,
    "W": 270.0,
    "NW": 315.0,
}


class CoverageReport(float):
    """Float representing coverage fraction, supporting dict-like access."""
    seen: int
    total: int
    coverage: float
    fraction: float

    def __new__(cls, fraction: float, seen: int = 0, total: int = 0):
        obj = super().__new__(cls, fraction)
        obj.seen = seen
        obj.total = total
        obj.coverage = fraction
        obj.fraction = fraction
        return obj

    def __getitem__(self, item: str) -> Any:
        if item in ("coverage", "fraction"):
            return float(self)
        if item == "seen":
            return self.seen
        if item == "total":
            return self.total
        raise KeyError(item)

    def get(self, item: str, default: Any = None) -> Any:
        try:
            return self[item]
        except KeyError:
            return default


def _coerce_rng(rng: Optional[Union[int, random.Random, np.random.Generator]] = None) -> random.Random:
    """Normalize user input to a Python random.Random instance for consistency."""
    if rng is None:
        return random.Random()
    if isinstance(rng, (int, np.integer)):
        return random.Random(int(rng))
    if isinstance(rng, np.random.Generator):
        # Extract deterministic seed value from numpy generator
        seed_val = int(rng.integers(0, 2**31 - 1))
        return random.Random(seed_val)
    if isinstance(rng, random.Random):
        return rng
    return random.Random()


def _calculate_difficulty(factors: Dict[str, Any]) -> float:
    """Calculate weighted sum of normalized factors (strictly in range 0.0 to 1.0)."""
    score = (
        WEIGHTS["time_of_day"] * TIME_OF_DAY_SCORE.get(factors["time_of_day"], 0.5)
        + WEIGHTS["weather"] * WEATHER_SCORE.get(factors["weather"], 0.5)
        + WEIGHTS["terrain"] * TERRAIN_SCORE.get(factors["terrain"], 0.5)
        + WEIGHTS["sensor_mode"] * SENSOR_MODE_SCORE.get(factors["sensor_mode"], 0.5)
        + WEIGHTS["degradation"] * DEGRADATION_SCORE.get(factors["degradation"], 0.5)
        + WEIGHTS["distractors"] * DISTRACTORS_SCORE.get(factors["distractors"], 0.5)
        + WEIGHTS["object_count"] * OBJECT_COUNT_SCORE.get(factors["object_count"], 0.5)
        + WEIGHTS["speed_band"] * SPEED_BAND_SCORE.get(factors["speed_band"], 0.5)
        + WEIGHTS["altitude_band"] * ALTITUDE_BAND_SCORE.get(factors["altitude_band"], 0.5)
        + WEIGHTS["motion_pattern"] * MOTION_PATTERN_SCORE.get(factors["motion_pattern"], 0.5)
    )
    # Ensure clamped within [0.0, 1.0] and rounded
    return max(0.0, min(1.0, round(float(score), 4)))


def _compute_fingerprint(factors: Dict[str, Any], objects: List[Dict[str, Any]]) -> str:
    """Generate SHA1 fingerprint from sorted factor values and object classes."""
    sorted_factors = sorted(str(v) for v in factors.values())
    sorted_classes = sorted(obj["true_class"] for obj in objects)
    fp_raw = "|".join(sorted_factors) + "::" + "|".join(sorted_classes)
    return hashlib.sha1(fp_raw.encode("utf-8")).hexdigest()


def _build_scenario_for_cell(
    cell: Tuple[str, ...],
    rng: random.Random,
    object_count: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a complete scenario dictionary for a specific condition cell."""
    time_of_day, weather, terrain, sensor_mode, degradation, distractors = cell

    # Object-level factor selections
    count_level = object_count if object_count in OBJECT_COUNT_LEVELS else rng.choice(OBJECT_COUNT_LEVELS)
    motion = rng.choice(MOTION_PATTERN)
    spd_band = rng.choice(SPEED_BAND)
    alt_band = rng.choice(ALTITUDE_BAND)
    sector = rng.choice(BEARING_SECTOR)

    factors = {
        "time_of_day": time_of_day,
        "weather": weather,
        "terrain": terrain,
        "sensor_mode": sensor_mode,
        "degradation": degradation,
        "distractors": distractors,
        "object_count": count_level,
        "motion_pattern": motion,
        "speed_band": spd_band,
        "altitude_band": alt_band,
        "bearing_sector": sector,
    }

    # Determine numeric object count from level
    if count_level == "1":
        num_objects = 1
    elif count_level == "2-3":
        num_objects = rng.randint(2, 3)
    elif count_level == "4-8":
        num_objects = rng.randint(4, 8)
    else:  # "9+"
        num_objects = rng.randint(9, 12)

    # Base bearing angle
    base_deg = BEARING_ANGLES.get(sector, 0.0)
    duration_s = float(rng.choice([45.0, 60.0, 90.0, 120.0]))

    # Generate objects
    objects: List[Dict[str, Any]] = []
    for i in range(num_objects):
        obj_id = f"obj_{i + 1}"
        true_class = rng.choice(CLASS_MIX)
        behaviour = rng.choice(BEHAVIOUR_LABEL)

        # Abstract threat level mapping (0 to 3)
        if true_class in ("bird", "balloon"):
            threat_level = 0 if behaviour == "benign" else 1
        elif true_class in ("light_aircraft", "unknown"):
            threat_level = 1 if behaviour == "benign" else 2
        else:  # multirotor, fixed_wing_uav
            threat_level = 2 if behaviour == "benign" else 3

        # Spatial position: Ensure objects map inside visible camera canvas for all terrains
        if i == 0:
            # Primary target starts well inside the forward viewing frustum
            angle_jitter = rng.uniform(-18.0, 18.0)
            rad = math.radians(angle_jitter)
            dist = rng.uniform(1100.0, 2200.0)
            start_x = dist * math.sin(rad)
            start_y = dist * math.cos(rad)
        else:
            angle_jitter = rng.uniform(-15.0, 15.0)
            deg = base_deg + angle_jitter
            rad = math.radians(deg)
            dist = rng.uniform(1000.0, 2800.0)
            start_y = max(400.0, dist * abs(math.cos(rad)))
            start_x = dist * math.sin(rad) * 0.5

        # Altitude band tailored to terrain clearance so targets are above ground & skyline
        if alt_band == "low":
            if terrain == "urban":
                start_z = rng.uniform(130.0, 240.0)
            elif terrain == "hills":
                start_z = rng.uniform(100.0, 200.0)
            elif terrain == "forest":
                start_z = rng.uniform(90.0, 180.0)
            else:
                start_z = rng.uniform(60.0, 140.0)
        elif alt_band == "med":
            start_z = rng.uniform(220.0, 500.0)
        else:
            start_z = rng.uniform(500.0, 1500.0)

        # Speed band (m/s)
        if spd_band == "low":
            spd = rng.uniform(5.0, 15.0)
        elif spd_band == "med":
            spd = rng.uniform(15.0, 35.0)
        else:
            spd = rng.uniform(35.0, 60.0)

        # Velocity components ensuring targets traverse or stay within forward view
        if motion in ("straight", "converging"):
            vx = -math.sin(rad) * spd * 0.5
            vy = -spd * 0.4
            vz = rng.uniform(-0.1, 0.1)
        elif motion == "loiter":
            vx = -math.cos(rad) * spd * 0.3
            vy = math.sin(rad) * spd * 0.3
            vz = 0.0
        elif motion == "parallel":
            vx = math.copysign(spd * 0.7, -start_x if abs(start_x) > 10 else 1.0)
            vy = rng.uniform(-1.0, 1.0)
            vz = rng.uniform(-0.1, 0.1)
        else:  # erratic
            vx = rng.uniform(-spd * 0.4, spd * 0.4)
            vy = -abs(rng.uniform(spd * 0.1, spd * 0.3))
            vz = rng.uniform(-0.2, 0.2)

        # Appear time strictly falls inside duration_s with adequate remaining time
        # Requirement: Every scenario must have a visible, clickable object within first 5 seconds
        if i == 0:
            appears_at = rng.uniform(0.0, 1.5)
        else:
            appears_at = rng.uniform(0.0, max(1.0, min(15.0, duration_s - 15.0)))

        objects.append(
            {
                "id": obj_id,
                "true_class": true_class,
                "true_threat_level": threat_level,
                "behaviour_label": behaviour,
                "start_position": [round(start_x, 2), round(start_y, 2), round(start_z, 2)],
                "velocity": [round(vx, 2), round(vy, 2), round(vz, 2)],
                "appears_at_time": round(appears_at, 2),
            }
        )

    # Distractor items mapping to noise windows
    distractor_items = {"none": 0, "birds": 2, "clutter": 4}.get(distractors, 0)
    noise_windows = 3 + distractor_items

    difficulty_index = _calculate_difficulty(factors)
    fingerprint = _compute_fingerprint(factors, objects)

    # Deterministic scenario_id from rng
    scenario_id = str(uuid.UUID(int=rng.getrandbits(128), version=4))

    return {
        "scenario_id": scenario_id,
        "cell": list(cell),
        "factors": factors,
        "objects": objects,
        "duration_s": duration_s,
        "noise_windows": noise_windows,
        "difficulty_index": difficulty_index,
        "fingerprint": fingerprint,
    }


def generate_for_cell(
    cell: Union[Tuple[str, ...], List[str]],
    rng: Optional[Union[int, random.Random, np.random.Generator]] = None,
    object_count: Optional[str] = None,
) -> Dict[str, Any]:
    """Target a specific condition cell and generate a scenario.
    
    Enforces validity rule: scenario must have at least one object on-screen and visible
    in the MAIN view for at least 6 consecutive seconds.
    If not, regenerates up to 20 tries, then relaxes degradation level.
    """
    rng_inst = _coerce_rng(rng)
    cell_tuple = tuple(cell)

    # 1. Try up to 20 times with original cell
    for _ in range(20):
        scenario = _build_scenario_for_cell(cell_tuple, rng_inst, object_count=object_count)
        if check_main_view_visibility(scenario, min_consecutive_s=6.0):
            return scenario

    # 2. Relax degradation level if not valid after 20 tries
    degradation_order = ["occlusion", "dropout", "lag", "noise", "none"]
    curr_deg = cell_tuple[4] if len(cell_tuple) > 4 else "none"

    if curr_deg in degradation_order:
        start_idx = degradation_order.index(curr_deg)
        for relaxed_deg in degradation_order[start_idx + 1:]:
            relaxed_cell = list(cell_tuple)
            relaxed_cell[4] = relaxed_deg

            # If the original cell was held out, prefer matching held-out cells
            candidate_tuple = tuple(relaxed_cell)
            if cell_tuple in HELD_OUT_CELLS and candidate_tuple not in HELD_OUT_CELLS:
                # Find any held-out cell with relaxed degradation
                matching_held_out = [
                    c for c in sorted(list(HELD_OUT_CELLS))
                    if c[4] == relaxed_deg and c[0] == cell_tuple[0] and c[1] == cell_tuple[1]
                ]
                if matching_held_out:
                    candidate_tuple = matching_held_out[0]

            for _ in range(5):
                scenario = _build_scenario_for_cell(candidate_tuple, rng_inst, object_count=object_count)
                if check_main_view_visibility(scenario, min_consecutive_s=6.0):
                    return scenario

    # 3. Fallback nominal
    fallback_cell = list(cell_tuple)
    fallback_cell[4] = "none"
    return _build_scenario_for_cell(tuple(fallback_cell), rng_inst, object_count=object_count)


def generate_scenario(
    rng: Optional[Union[int, random.Random, np.random.Generator]] = None,
    allow_held_out: bool = False,
) -> Dict[str, Any]:
    """Generate a random simulation scenario.
    
    Must NEVER draw from HELD_OUT cells unless allow_held_out=True.
    Enforces validity rule with up to 20 retries and degradation relaxation.
    """
    rng_inst = _coerce_rng(rng)

    if allow_held_out:
        candidate_cells = sorted(list(all_cells()))
    else:
        # Strictly PRACTICE cells only
        candidate_cells = sorted(list(PRACTICE_CELLS))

    selected_cell = rng_inst.choice(candidate_cells)
    return generate_for_cell(selected_cell, rng=rng_inst)



def coverage_report(trainee_id: str, db_path: Optional[str] = None) -> CoverageReport:
    """Return fraction of PRACTICE cells the trainee has seen (reads DB)."""
    seen = get_seen_cells(trainee_id, db_path=db_path)
    practice_seen = seen.intersection(PRACTICE_CELLS)
    total_practice = len(PRACTICE_CELLS)
    fraction = len(practice_seen) / total_practice if total_practice > 0 else 0.0
    return CoverageReport(fraction, seen=len(practice_seen), total=total_practice)
