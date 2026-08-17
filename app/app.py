# app.py — G-ASET Scoring & Improvement Planner (Shiny Express / shinylive)
from pathlib import Path
import csv, io, re, datetime as dt

import pandas as pd
import yaml
from pypdf import PdfReader
from shiny import reactive
from shiny.express import input, render, ui

import scoring
from scoring import QUESTIONS, DOMAIN_NAMES, DOMAIN_ITEMS
from i18n import detect_language, t

APP_DIR = Path(__file__).parent
FIELD_MAP = yaml.safe_load((APP_DIR / "field_map.yml").read_text(encoding="utf-8")) or {}
ACTION_PLAN = yaml.safe_load((APP_DIR / "action_plan.yml").read_text(encoding="utf-8"))

# ------------------------------------------------------------------ parsing
_CHECKED = {"/Yes", "Yes", "/On", "On", "/1", "1", "X", "/Checked"}

# Y/P/N precedence ordered from MOST to LEAST generous. Used for conflict
# resolution: when multiple boxes are checked, the LAST match (lowest score)
# wins — conservative by design, so contradictions can't inflate scores.
_YPN_ORDER = ("yes", "partial", "no")

def _is_checked(v) -> bool:
    return v is not None and str(v) in _CHECKED


def _parse_date(s: str, dayfirst: bool = False):
    """Parse a single date string. dayfirst=True interprets 09/12/2025 as 9 Dec."""
    s = s or ""
    m = re.search(r"\d{4}-\d{2}-\d{2}", s)
    if m:
        try:
            return dt.datetime.strptime(m.group(0), "%Y-%m-%d").date()
        except ValueError:
            pass
    m = re.search(r"\d{1,2}/\d{1,2}/\d{4}", s)
    if m:
        fmt = "%d/%m/%Y" if dayfirst else "%m/%d/%Y"
        try:
            return dt.datetime.strptime(m.group(0), fmt).date()
        except ValueError:
            # e.g. 25/09/2025 parsed with %m/%d -> retry the other convention
            alt = "%m/%d/%Y" if dayfirst else "%d/%m/%Y"
            try:
                return dt.datetime.strptime(m.group(0), alt).date()
            except ValueError:
                pass
    return None

def _all_dates(strings, dayfirst: bool = False) -> list:
    """Parse every date found across a list of strings."""
    found = []
    for s in strings:
        d = _parse_date(str(s), dayfirst)
        if d:
            found.append(d)
    return found

def parse_pdf(data: bytes, filename: str, dayfirst: bool = False) -> dict:
    """
    Parse a completed G-ASET fillable PDF into a response dict.
    Args:
        data:     raw PDF bytes
        filename: original filename (used as facility-name fallback)
        dayfirst: date convention — False = MM/DD/YYYY (US), True = DD/MM/YYYY.
                  Wire this to the sidebar toggle: input.date_format() == "dmy"
    Returns dict with keys:
        facility, date, lang, responses {item: value}, conflicts [ {...} ],
        raw_fields {name: value}, source
    """
    reader = PdfReader(io.BytesIO(data))
    # -- Language detection from page text (drives UI translation) ----------
    text = " ".join((p.extract_text() or "") for p in reader.pages)
    lang = detect_language(text)
    # -- Raw AcroForm field dump (also feeds the Field Inspector) -----------
    fields = reader.get_fields() or {}
    values = {
        k: (f.get("/V") if hasattr(f, "get") else getattr(f, "value", None))
        for k, f in fields.items()
    }
    # -- Config-driven policies ----------------------------------------------
    # field_map.yml (top level):  policies: {na_conflict: count_selections|na_wins}
    na_policy = FIELD_MAP.get("policies", {}).get("na_conflict", "count_selections")
    fmap = FIELD_MAP.get("items", {})
    responses: dict[int, object] = {}
    conflicts: list[dict] = []
    for item_str, spec in fmap.items():
        item = int(item_str)
        kind = spec.get("type")
        # ---- Yes / Partially / No as three independent checkboxes ---------
        if kind == "ypn":
            checked = [k for k in _YPN_ORDER if _is_checked(values.get(spec.get(k)))]
            if len(checked) > 1:
                # Contradiction (e.g., Yes AND No both checked, as seen in the
                # completed example's item 6C). Conservative resolution: the
                # lowest-scoring checked option wins, and we flag it loudly.
                responses[item] = checked[-1]
                conflicts.append({
                    "item": item,
                    "issue": f"multiple Y/P/N selections checked: {checked}",
                    "resolution": f"scored conservatively as '{checked[-1]}'",
                })
            elif checked:
                responses[item] = checked[0]
            else:
                # Nothing checked = element not in place -> "No" per rubric.
                # (If the field map is unresolved this also lands here — the
                # field-map validator is what distinguishes the two cases.)
                responses[item] = "no"
        # ---- Yes / Partially / No as a single radio-group field -----------
        # field_map.yml form:
        #   type: ypn_radio
        #   field: "Q1_Group"
        #   values: {yes: "/Yes", partial: "/Partially", no: "/No"}
        elif kind == "ypn_radio":
            v = str(values.get(spec.get("field"), ""))
            vmap = spec.get("values", {})
            responses[item] = next(
                (k for k, ev in vmap.items() if v == str(ev)), "no"
            )
        # ---- Select-all-that-apply (count, composite, required-set) -------
        elif kind == "multi":
            sels = [key for key, fname in spec.get("options", {}).items()
                    if _is_checked(values.get(fname))]
            if "not_applicable" in sels and len(sels) > 1:
                # NA checked alongside real selections (seen in item 31 of the
                # completed example: UTI + "Not applicable" both checked).
                conflicts.append({
                    "item": item,
                    "issue": "'Not applicable' checked alongside real selections",
                    "resolution": ("NA ignored; selections scored"
                                   if na_policy == "count_selections"
                                   else "NA wins; item scored 0"),
                })
                if na_policy == "count_selections":
                    sels = [s for s in sels if s != "not_applicable"]
                else:  # na_wins
                    sels = ["not_applicable"]
            responses[item] = sels
        # ---- Item 35A: count of "Yes" checkboxes across activities A–R ----
        elif kind == "yescount":
            responses[item] = sum(
                _is_checked(values.get(f)) for f in spec.get("yes_fields", [])
            )
        else:
            conflicts.append({
                "item": item,
                "issue": f"unknown field-map type '{kind}'",
                "resolution": "item skipped — fix field_map.yml",
            })
    # -- Facility name: mapped field first, then text regex, then filename --
    meta = FIELD_MAP.get("meta", {})
    facility = str(values.get(meta.get("facility_field"), "") or "").strip()
    if not facility:
        m = re.search(r"Facility Name:\s*([^\n]+)", text)
        facility = m.group(1).strip() if m else filename.rsplit(".", 1)[0]
    # -- Completion date: the respondent table has one date row PER DOMAIN, --
    # -- so collect ALL date-bearing fields and take the LATEST as the      --
    # -- assessment completion date. Fall back to dates found in page text. --
    date_field_names = meta.get("date_fields") or (
        [meta["date_field"]] if meta.get("date_field") else []
    )
    date_candidates = _all_dates(
        [values.get(n, "") for n in date_field_names], dayfirst
    )
    if not date_candidates:
        date_candidates = _all_dates(
            re.findall(r"\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2}", text), dayfirst
        )
    date = max(date_candidates) if date_candidates else dt.date.today()
    return {
        "facility": facility,
        "date": date,
        "lang": lang,
        "responses": responses,
        "conflicts": conflicts,
        "raw_fields": values,
        "source": filename,
    }

def parse_csv(data: bytes, filename: str) -> dict:
    """Fallback format: rows of item,response.
       ypn -> yes|partial|no ; multi -> 'opt1;opt2' ; item 35 -> integer yes-count."""
    responses, facility, date = {}, filename.rsplit(".", 1)[0], dt.date.today()
    for row in csv.DictReader(io.StringIO(data.decode("utf-8-sig"))):
        key = (row.get("item") or "").strip().lower()
        val = (row.get("response") or "").strip()
        if key == "facility":
            facility = val
        elif key == "date":
            date = _parse_date(val) or date
        elif key.isdigit():
            item = int(key)
            if item in scoring.YPN_ITEMS:
                responses[item] = val.lower()
            elif item in scoring.YESCOUNT_ITEMS:
                responses[item] = int(val or 0)
            else:
                responses[item] = [v.strip() for v in val.split(";") if v.strip()]
    return {"facility": facility, "date": date, "lang": "en",
            "responses": responses, "raw_fields": {}, "source": filename}

def validate_field_map(pdf_field_names: set[str]) -> pd.DataFrame:
    """Flags placeholder or missing field names so SMEs see mapping gaps."""
    problems = []
    for item, spec in FIELD_MAP.get("items", {}).items():
        names = ([spec.get(k) for k in ("yes", "partial", "no")] if spec["type"] == "ypn"
                 else spec.get("yes_fields", []) if spec["type"] == "yescount"
                 else list(spec.get("options", {}).values()))
        for n in names:
            if not n or n.startswith("REPLACE__"):
                problems.append({"item": item, "field": n, "issue": "placeholder — not yet mapped"})
            elif pdf_field_names and n not in pdf_field_names:
                problems.append({"item": item, "field": n, "issue": "not found in uploaded PDF"})
    return pd.DataFrame(problems)

# ------------------------------------------------------------------ reactives

@reactive.calc
def assessments():
    try:
        files = input.files()
    except Exception:
        return []
    if not files:
        return []
    dayfirst = input.date_format() == "dmy"
    out = []
    for f in files:
        data = Path(f["datapath"]).read_bytes()
        try:
            rec = (parse_pdf(data, f["name"], dayfirst=dayfirst)
                   if f["name"].lower().endswith(".pdf")
                   else parse_csv(data, f["name"]))
            rec["scores"] = scoring.score_assessment(rec["responses"])
            out.append(rec)
        except Exception as e:
            out.append({"facility": f["name"], "date": dt.date.today(), "lang": "en",
                        "responses": {}, "conflicts": [], "raw_fields": {},
                        "source": f["name"], "error": str(e),
                        "scores": scoring.score_assessment({})})
    return sorted(out, key=lambda r: (r["facility"], r["date"]))

@reactive.calc
def lang():
    a = assessments()
    return a[-1]["lang"] if a else "en"

@reactive.calc
def current():
    a = assessments()
    if not a:
        return None
    try:
        sel = input.which()
    except Exception:   # SilentException before the dynamic select renders
        sel = None
    for rec in a:
        if rec["source"] == sel:
            return rec
    return a[-1]        # sensible default: most recent assessment

def rec_text(item: int, lg: str) -> str:
    entry = ACTION_PLAN.get("recommendations", {}).get(str(item), {})
    return entry.get(lg) or entry.get("en") or QUESTIONS[item]

def rec_tier(item: int, points: float) -> str:
    entry = ACTION_PLAN.get("recommendations", {}).get(str(item), {})
    d = ACTION_PLAN.get("defaults", {})
    if points == 0:
        return entry.get("gap_tier", d.get("gap_tier", "high"))
    return entry.get("partial_tier", d.get("partial_tier", "medium"))

@reactive.calc
def plan_df():
    rec = current()
    if rec is None:
        return pd.DataFrame()
    lg, order = rec["lang"], ACTION_PLAN.get("priority_order", ["critical", "high", "medium", "low"])
    rows = []
    for item, pts in rec["scores"]["items"].items():
        if pts >= 5:
            continue
        rows.append({
            t(lg, "priority"): rec_tier(item, pts),
            t(lg, "domain"): DOMAIN_NAMES[next(d for d, its in DOMAIN_ITEMS.items() if item in its)],
            t(lg, "item"): item,
            t(lg, "question"): QUESTIONS[item],
            "Status": t(lg, "gap") if pts == 0 else t(lg, "partial_gap"),
            t(lg, "recommendation"): rec_text(item, lg),
            "_rank": order.index(rec_tier(item, pts)) if rec_tier(item, pts) in order else 99,
            "_pts": pts,
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["_rank", "_pts"]).drop(columns=["_rank", "_pts"])
    return df

# ------------------------------------------------------------------ UI
ui.page_opts(title="G-ASET", fillable=False)

with ui.sidebar(width=340):
    ui.input_file(
        "files",
        "Upload completed G-ASET file(s) (PDF or CSV)",  # English default label
        accept=[".pdf", ".csv"],
        multiple=True,)

    ui.input_radio_buttons(
    "date_format", "Date format in uploaded PDFs",
    {"mdy": "MM/DD/YYYY", "dmy": "DD/MM/YYYY"}, selected="mdy",)


    @render.ui
    def _upload_hint():
        lg = lang()
        return ui.p(t(lg, "upload"), style="font-size:0.85em; color:#555;") \
            if lg != "en" else None
    @render.ui
    def _selector():
        a = assessments()
        if not a:
            return ui.p(t("en", "no_files"))
        choices = {r["source"]: f'{r["facility"]} — {r["date"]}' for r in a}
        return ui.input_select("which", t(lang(), "select_assessment"),
                               choices, selected=a[-1]["source"])
    @render.ui
    def _note():
        return ui.p(ui.em(t(lang(), "internal_use")), style="font-size:0.85em;")


with ui.nav_panel("📊"):
    @render.ui
    def scores_header():
        rec = current()
        if rec is None:
            return ui.h4(t(lang(), "tab_scores"))
        lg, ov = rec["lang"], rec["scores"]["overall"]
        return ui.TagList(
            ui.h3(t(lg, "app_title")),
            ui.layout_columns(
                ui.value_box(t(lg, "overall"), f'{ov["pct"]}%',
                             f'{ov["earned"]:g} / {ov["max"]}'),
                ui.value_box(t(lg, "facility"), rec["facility"], str(rec["date"])),
            ),
        )

    @render.data_frame
    def domain_table():
        rec = current()
        if rec is None:
            return pd.DataFrame()
        lg = rec["lang"]
        rows = [{t(lg, "domain"): f"{d}. {DOMAIN_NAMES[d]}",
                 t(lg, "earned"): f'{v["earned"]:g}',
                 t(lg, "max"): v["max"],
                 t(lg, "pct"): f'{v["pct"]}%'}
                for d, v in rec["scores"]["domains"].items()]
        return pd.DataFrame(rows)

    @render.data_frame
    def item_table():
        rec = current()
        if rec is None:
            return pd.DataFrame()
        lg = rec["lang"]
        rows = [{t(lg, "domain"): d,
                 t(lg, "item"): i,
                 t(lg, "question"): QUESTIONS[i],
                 t(lg, "points"): f'{rec["scores"]["items"][i]:g} / 5'}
                for d, items in DOMAIN_ITEMS.items() for i in items]
        return pd.DataFrame(rows)

    with ui.accordion(open=False):
        with ui.accordion_panel("🔧 Field inspector"):
            @render.data_frame
            def inspector():
                rec = current()
                if rec is None or not rec.get("raw_fields"):
                    return pd.DataFrame({"info": ["No AcroForm fields detected."]})
                return pd.DataFrame(
                    [{"field": k, "value": str(v)} for k, v in rec["raw_fields"].items()]
                )
            @render.data_frame
            def response_conflicts():
                rec = current()
                if rec is None or not rec.get("conflicts"):
                    return pd.DataFrame()
                return pd.DataFrame(rec["conflicts"])

            @render.ui
            def conflict_banner():
                rec = current()
                if rec and rec.get("conflicts"):
                    return ui.div(
                        f"⚠️ {len(rec['conflicts'])} contradictory response(s) detected "
                        "(e.g., Yes and No both checked). They were scored per the stated "
                        "policy — consider correcting the PDF and re-uploading.",
                        class_="alert alert-warning")
                return None

with ui.nav_panel("📈"):
    @render.ui
    def trend_note():
        return ui.p(t(lang(), "trend_hint"))

    @render.plot
    def trend_plot():
        import matplotlib.pyplot as plt
        a = assessments()
        fig, ax = plt.subplots(figsize=(9, 5))
        if len(a) >= 2:
            rec = current()
            fac = rec["facility"] if rec else a[-1]["facility"]
            series = [r for r in a if r["facility"] == fac]
            dates = [r["date"] for r in series]
            for d in DOMAIN_ITEMS:
                ax.plot(dates, [r["scores"]["domains"][d]["pct"] for r in series],
                        marker="o", label=f"D{d}: {DOMAIN_NAMES[d]}")
            ax.plot(dates, [r["scores"]["overall"]["pct"] for r in series],
                    marker="s", linewidth=3, color="black", label="Overall")
            ax.set_ylim(0, 100); ax.set_ylabel("%"); ax.set_title(fac)
            ax.legend(fontsize=7, loc="lower right"); fig.autofmt_xdate()
        return fig

    @render.data_frame
    def trend_table():
        a = assessments()
        if not a:
            return pd.DataFrame()
        lg = lang()
        return pd.DataFrame([{
            t(lg, "facility"): r["facility"], t(lg, "date"): str(r["date"]),
            **{f"D{d} %": r["scores"]["domains"][d]["pct"] for d in DOMAIN_ITEMS},
            t(lg, "overall"): f'{r["scores"]["overall"]["pct"]}%'} for r in a])

with ui.nav_panel("🗺️"):
    @render.ui
    def plan_intro():
        return ui.p(t(lang(), "plan_intro"))

    @render.data_frame
    def plan_table():
        return plan_df()

    @render.download(label="⬇ CSV", filename="gaset_action_plan.csv")
    def download_plan():
        yield plan_df().to_csv(index=False)