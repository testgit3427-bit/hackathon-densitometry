TEMPLATE = (
    "You are a radiology quality assurance expert. Analyze this Bone Densitometry (DXA) scan image for procedural correctness.\n"
    "Evaluate and report on the following criteria for the {anatomy_zone} region:\n"
    "1. Patient Positioning: {specific_guidelines}\n"
    "2. ROI (Region of Interest) Compatibility: Is the bone visibility clear enough "
    "to place measurement boxes and baseline markers properly? Are there any overlapping "
    "structures, motion blurs, or external artifacts (e.g., buttons, implants) that would block ROI selection?\n"
    "3. Scan Completeness: Are all required anatomical landmarks for this specific region "
    "fully visible and included in the field of view?\n"
    "\n"
    "Write your analysis in Russian.\n"
    "At the very end of your response, add a final line with EXACTLY one of these two options:\n"
    "DECISION: ACCEPTED\n"
    "or\n"
    "DECISION: REJECTED\n"
    "Do not add anything after this line. The word ACCEPTED means the scan is suitable for diagnostic evaluation. "
    "The word REJECTED means the scan has technical errors and must be repeated."
)

ZONE_GUIDELINES = {
    "LUMBAR_SPINE": {
        "label": "lumbar spine (L1-L4)",
        "zone_ru": "Поясничный отдел позвоночника (L1-L4)",
        "positioning": (
            "The patient lies supine, centered on the scanning table with the lumbar spine aligned "
            "along the midline. Both lower limbs are elevated on a positioning block to flatten the "
            "lumbar lordosis, and the pelvis must be level with the torso straight. The scan must be "
            "performed perpendicular to the spine axis; no lateral torso rotation or tilt greater than "
            "10 degrees is acceptable. The L1-L4 scan region must be entered in the correct anatomical "
            "order with no segment overlap."
        ),
    },
    "HIP": {
        "label": "hip (femoral neck)",
        "zone_ru": "Тазобедренный сустав (шейка бедра)",
        "positioning": (
            "The patient lies supine with the examined leg internally rotated 15-25 degrees using the "
            "positioning foot device, so the femoral neck is projected along its true axis with maximal "
            "length and the femur shaft parallel to the table edge. The pelvis must be level and the "
            "contralateral leg neutral. The scan field must start below the femoral head and the neck "
            "must not be foreshortened or hidden behind the greater trochanter."
        ),
    },
    "HIP_RIGHT": {
        "label": "right hip (femoral neck)",
        "zone_ru": "Тазобедренный сустав (справа, шейка бедра)",
        "positioning": (
            "The patient lies supine with the examined RIGHT leg internally rotated 15-25 degrees using the "
            "positioning foot device, so the femoral neck is projected along its true axis with maximal "
            "length and the femur shaft parallel to the table edge. The pelvis must be level and the "
            "contralateral leg neutral. The scan field must start below the femoral head and the neck "
            "must not be foreshortened or hidden behind the greater trochanter."
        ),
    },
    "HIP_LEFT": {
        "label": "left hip (femoral neck)",
        "zone_ru": "Тазобедренный сустав (слева, шейка бедра)",
        "positioning": (
            "The patient lies supine with the examined LEFT leg internally rotated 15-25 degrees using the "
            "positioning foot device, so the femoral neck is projected along its true axis with maximal "
            "length and the femur shaft parallel to the table edge. The pelvis must be level and the "
            "contralateral leg neutral. The scan field must start below the femoral head and the neck "
            "must not be foreshortened or hidden behind the greater trochanter."
        ),
    },
    "FOREARM": {
        "label": "forearm (radius/ulna)",
        "zone_ru": "Предплечье (лучевая/локтевая кость)",
        "positioning": (
            "The patient sits beside the scanner and places the forearm flat in the center of the table "
            "in mid-pronation position, with the elbow flexed to 90 degrees. Midline of the forearm must "
            "be parallel to the scan field, without supination or pronation deviation, and the radius and "
            "ulna should not overlap. The shoulder must be relaxed to avoid motion during the scan."
        ),
    },
    "WHOLE_BODY": {
        "label": "whole body",
        "zone_ru": "Всё тело (total body)",
        "positioning": (
            "The patient lies supine centered in the scan field, head straight, arms positioned according "
            "to the protocol away from the trunk (thumbs on mid-thigh line or extended elbow positions), "
            "and legs together with slight internal rotation. Both hands, feet and the entire head must be "
            "fully included; the body must fit within the total body scan lines without cutoff at the ends."
        ),
    },
    "VFA": {
        "label": "vertebral fracture assessment (VFA, lateral spine)",
        "zone_ru": "Вертебральная оценка переломов (VFA, боковая проекция)",
        "positioning": (
            "The patient lies in lateral decubitus position, centered, with arms raised above the head so "
            "the arms and ribs do not overlap the spine, and legs slightly flexed for stability. The spine "
            "from the mid-thoracic to the lumbar region (ideally T4-L4) must be imaged in one continuous "
            "field. No patient rotation/parallax between vertebral segments is allowed; the scan must be "
            "free of barium/artifact shadows from lungs that obscure vertebral endplates."
        ),
    },
    "UNKNOWN": {
        "label": "general DXA",
        "zone_ru": "Не определена (общий протокол)",
        "positioning": (
            "The patient must be centered on the imaging table with the examined region fully in the "
            "field of view, limbs positioned according to the standard protocol for the region, and no "
            "foreign objects (buttons, zippers, implants, jewelry) inside the scan area. The region of "
            "interest must be clearly separated from neighboring structures with no motion artifacts."
        ),
    },
}

_MATCHERS = [
    ("VFA", ("vfa", "vertebral fracture", "thoraco",
             "lateral spine", "l2-l4 lateral", "lateral lumbar")),
    ("WHOLE_BODY", ("whole body", "total body", "whole", "total", "body")),
    ("FOREARM", ("forearm", "radius", "ulna", "wrist", "forearm (radius/ulna)")),
    ("HIP_LEFT", ("left hip", "hip left", "left femur", "femur left",
                  "left proximal", "proximal femoral left", "left neck")),
    ("HIP_RIGHT", ("right hip", "hip right", "right femur", "femur right",
                   "right proximal", "proximal femoral right", "right neck")),
    ("HIP", ("hip", "femur", "proximal femoral", "femoral neck", "neck", "left hip", "right hip")),
    ("LUMBAR_SPINE", ("lumbar", "spine", "l1-l4", "l1", "l2", "l3", "l4", "l1l4", "ap")) 
]


def detect_zone(meta=None):
    meta = meta or {}
    hay = " ".join(
        str(meta.get(field) or "").lower()
        for field in (
            "body_part",
            "study_description",
            "protocol_name",
            "view_position",
            "image_type",
            "series_description",
            "modality",
        )
    )
    for key, markers in _MATCHERS:
        if any(marker in hay for marker in markers):
            return key
    return "UNKNOWN"


def zone_label(zone_key):
    return ZONE_GUIDELINES.get(zone_key, ZONE_GUIDELINES["UNKNOWN"])["zone_ru"]


def build_prompt(zone_key, meta=None):
    zone = ZONE_GUIDELINES.get(zone_key, ZONE_GUIDELINES["UNKNOWN"])
    prompt = TEMPLATE.replace("{anatomy_zone}", zone["label"])
    prompt = prompt.replace("{specific_guidelines}", zone["positioning"])
    return prompt