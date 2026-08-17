# scoring.py
"""G-ASET scoring engine — implements CDC Scoring Rubric (CS350617-B 11/1/2024)."""

DOMAIN_NAMES = {
    1: "Leadership Commitment & Accountability",
    2: "Resources",
    3: "Education & Training",
    4: "Antibiotic Stewardship Actions",
    5: "Antibiotic Use Tracking, Monitoring, & Reporting",
}
DOMAIN_ITEMS = {
    1: list(range(1, 13)),
    2: list(range(13, 26)),
    3: list(range(26, 31)),
    4: list(range(31, 52)),
    5: list(range(52, 67)),
}
DOMAIN_MAX = {1: 60, 2: 65, 3: 25, 4: 105, 5: 75}
OVERALL_MAX = 330

# --- Item type registries -------------------------------------------------
# Count items: {item: threshold_for_5_points}; 2.5 pts if >=1 but < threshold
COUNT_ITEMS = {4: 8, 9: 2, 18: 2, 19: 2, 31: 4, 37: 2, 38: 2, 43: 2, 58: 2, 59: 2}
ANY_ITEMS = {54}                 # >=1 selected = 5, else 0 (no partial credit)
COMPOSITE_ITEMS = {6, 11, 14}    # personnel composition rule
YESCOUNT_ITEMS = {35: 9}         # item 35A: >=9 "yes" = 5; 1-8 = 2.5; 0 = 0
REQUIRED_SET_ITEMS = {32: {"first_line", "dose", "duration", "alternatives"}}

_SPECIAL = set(COUNT_ITEMS) | ANY_ITEMS | COMPOSITE_ITEMS | set(YESCOUNT_ITEMS) | set(REQUIRED_SET_ITEMS)
YPN_ITEMS = {i for i in range(1, 67) if i not in _SPECIAL}

# Composite rule (items 6A, 11, 14):
#   5   = ID-trained physician AND (ID pharmacist OR clinical pharmacist OR staff
#         pharmacist)* AND clinical microbiologist*   (*if present at HCF — see note)
#   2.5 = anything selected not meeting criteria
#   0   = none / not applicable
# NOTE: the rubric conditions pharmacist/microbiologist requirements on their
# presence at the HCF (item 14). Set `pharmacist_at_hcf` / `micro_at_hcf` flags
# from item 14 responses to honor the conditional; defaults assume both present
# (conservative scoring).
COMPOSITE_KEYS = {
    "physician": {"id_physician"},
    "pharmacist": {"id_pharmacist", "clinical_pharmacist", "staff_pharmacist"},
    "micro": {"microbiologist"},
}


def score_ypn(resp: str) -> float:
    return {"yes": 5.0, "partial": 2.5, "no": 0.0}.get((resp or "no").lower(), 0.0)


def score_count(item: int, selections: list) -> float:
    sels = [s for s in (selections or []) if s and s != "not_applicable"]
    n = len(sels)
    if n == 0:
        return 0.0
    if item in ANY_ITEMS:
        return 5.0
    thr = COUNT_ITEMS[item]
    return 5.0 if n >= thr else 2.5


def score_composite(selections: list, pharmacist_at_hcf=True, micro_at_hcf=True) -> float:
    sels = set(selections or [])
    if not sels or sels == {"not_applicable"}:
        return 0.0
    ok_phys = bool(sels & COMPOSITE_KEYS["physician"])
    ok_pharm = (not pharmacist_at_hcf) or bool(sels & COMPOSITE_KEYS["pharmacist"])
    ok_micro = (not micro_at_hcf) or bool(sels & COMPOSITE_KEYS["micro"])
    return 5.0 if (ok_phys and ok_pharm and ok_micro) else 2.5


def score_required_set(item: int, selections: list) -> float:
    sels = set(selections or []) - {"not_applicable"}
    if not sels:
        return 0.0
    return 5.0 if REQUIRED_SET_ITEMS[item] <= sels else 2.5


def score_yescount(item: int, n_yes: int) -> float:
    if n_yes >= YESCOUNT_ITEMS[item]:
        return 5.0
    return 2.5 if n_yes >= 1 else 0.0


def score_item(item: int, response, ctx: dict | None = None) -> float:
    ctx = ctx or {}
    if item in YPN_ITEMS:
        return score_ypn(response)
    if item in COMPOSITE_ITEMS:
        return score_composite(response,
                               ctx.get("pharmacist_at_hcf", True),
                               ctx.get("micro_at_hcf", True))
    if item in REQUIRED_SET_ITEMS:
        return score_required_set(item, response)
    if item in YESCOUNT_ITEMS:
        return score_yescount(item, int(response or 0))
    if item in COUNT_ITEMS or item in ANY_ITEMS:
        return score_count(item, response)
    raise ValueError(f"Unknown item {item}")


def score_assessment(responses: dict) -> dict:
    """responses: {item_number: response}. Returns per-item, per-domain, overall."""
    # Derive presence flags from item 14 for the composite conditional
    it14 = responses.get(14) or []
    ctx = {
        "pharmacist_at_hcf": bool(set(it14) & COMPOSITE_KEYS["pharmacist"]) or not it14,
        "micro_at_hcf": ("microbiologist" in it14) or not it14,
    }
    item_pts = {i: score_item(i, responses.get(i), ctx) for i in range(1, 67)}
    domains = {}
    for d, items in DOMAIN_ITEMS.items():
        earned = sum(item_pts[i] for i in items)
        domains[d] = {"earned": earned, "max": DOMAIN_MAX[d],
                      "pct": round(100 * earned / DOMAIN_MAX[d], 1)}
    overall = sum(v["earned"] for v in domains.values())
    return {"items": item_pts, "domains": domains,
            "overall": {"earned": overall, "max": OVERALL_MAX,
                        "pct": round(100 * overall / OVERALL_MAX, 1)}}


# Concise question text (English canonical; other languages come from i18n)
QUESTIONS = {
    1: "Antibiotic stewardship identified as a priority by facility leadership?",
    2: "Stewardship activities in facility annual plans with KPIs?",
    3: "Antibiotic stewardship committee reviewing policies/guidelines?",
    4: "Members of the stewardship committee (select all that apply)",
    5: "Committee meets regularly (minimum quarterly)?",
    6: "Antibiotic stewardship team composition (6A)",
    7: "Stewardship team meets on a regular basis?",
    8: "Committee/team has authority over antibiotic-use policies?",
    9: "Departments the committee/team collaborates with",
    10: "Participation in external stewardship networks?",
    11: "Who is involved in formulary/procurement decisions",
    12: "Safety/efficacy/cost evidence evaluated before formulary addition?",
    13: "Human and financial resources allocated for stewardship?",
    14: "Personnel physically present at the facility",
    15: "Team has office/physical space for stewardship activities?",
    16: "Team has basic equipment (telephone, computer)?",
    17: "Information/decision-support systems supporting stewardship?",
    18: "Data/records the stewardship team can access",
    19: "Data available electronically at the facility",
    20: "Access to updated peer-reviewed scientific literature?",
    21: "Access to laboratory and imaging services?",
    22: "Microbiology lab open 24 hours/day?",
    23: "Microbiology lab accredited?",
    24: "Microbiology lab has a quality control system?",
    25: "Microbiology lab has an electronic laboratory information system?",
    26: "Stewardship training included in staff induction/new-hire training?",
    27: "Continuous in-service training on stewardship AND IPC?",
    28: "Stewardship training for students/trainees?",
    29: "Training for the stewardship team on stewardship/IPC?",
    30: "Patient/family education about antibiotics?",
    31: "Treatment guidelines that exist at the facility",
    32: "Contents of treatment guidelines (agent, dose, duration, alternatives)",
    33: "Guidelines reviewed/updated periodically and communicated?",
    34: "Antibiogram used to modify treatment guidelines?",
    35: "Routine stewardship activities conducted (35A, of 18 listed)",
    36: "Standard operating procedures for stewardship activities?",
    37: "Contents of the stewardship activity report",
    38: "Recipients of the stewardship activity report",
    39: "Formulary/list of approved antibiotics based on national formulary?",
    40: "Formulary specifies restricted antibiotics requiring pre-authorization?",
    41: "Approval of restricted antibiotics available throughout the workday?",
    42: "Formulary modifications communicated to prescribers?",
    43: "Nurse-led stewardship activities",
    44: "Policy requiring documentation of dose, duration, indication?",
    45: "Lab uses rapid diagnostic testing for early antibiotic adjustment?",
    46: "Lab can identify key resistance mechanisms (ESBL, carbapenemases)?",
    47: "Culture & susceptibility results provided in a timely manner (≤72h)?",
    48: "Selective or cascading susceptibility reporting used?",
    49: "Lab adds comments in culture results to improve prescribing?",
    50: "Emergence of new resistance communicated to prescribers?",
    51: "Analysis of barriers/challenges/opportunities conducted?",
    52: "Regular prescription audits / point prevalence surveys?",
    53: "Quantity and types of antibiotic use regularly monitored/reported?",
    54: "Metric used for antibiotic use/consumption (DOT, DDD)",
    55: "Action plans developed to address identified problems?",
    56: "Compliance with ≥1 stewardship activity monitored?",
    57: "Strategies implemented to increase compliance?",
    58: "Metrics monitored to assess stewardship impact",
    59: "Data stratifiable by hospital unit/ward",
    60: "Shortages/stockouts of essential antibiotics monitored?",
    61: "Shortages/stockouts of laboratory supplies monitored?",
    62: "Mechanism to report substandard antibiotics/diagnostics?",
    63: "Susceptibility/resistance rates for key bacteria monitored/reported?",
    64: "Audit findings communicated to prescribers with action points?",
    65: "Impact metrics reported to facility leadership?",
    66: "Antibiogram developed, aggregated, and regularly updated?",
}