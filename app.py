"""Streamlit view over results/results.json.

Deliberately thin. Every number here was computed by audit.py and written to
results.json -- this file reads and displays, it never recomputes. The static
report at results/report.html shows the same figures with no install required;
this exists for filtering and poking at individual conversations.

    pip install streamlit && streamlit run app.py
"""

import json
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent
RESULTS = ROOT / "results" / "results.json"
DATA = ROOT / "data" / "conversations.jsonl"

st.set_page_config(page_title="Deflection Audit", layout="wide")

if not RESULTS.exists():
    st.error("No results yet. Run `python audit.py --replay` first.")
    st.stop()

data = json.loads(RESULTS.read_text())
records = {json.loads(line)["id"]: json.loads(line) for line in DATA.open()}

st.title("Deflection Audit")
st.caption("What the deployment counted as deflected, versus what actually resolved.")

a, b, c = st.columns(3)
a.metric("Claimed deflection", f"{data['claimed_rate']:.1%}",
         help=f"{data['claimed_deflected']} of {data['total']} closed without handoff")
b.metric("Audited deflection", f"{data['audited_rate']:.1%}",
         delta=f"-{data['inflation_points']:.1f} pts",
         delta_color="inverse",
         help=f"{data['audited_resolved']} of {data['total']} genuinely resolved")
c.metric("Overstatement", f"{data['overstatement_factor']:.2f}x",
         help="claimed rate as a multiple of the audited rate")

st.subheader("Where the claimed deflections went")
st.bar_chart(
    {
        "conversations": {
            "resolved": data["audited_resolved"],
            "partial": data["partial"],
            "false deflection": data["false_deflections"],
        }
    },
    horizontal=True,
)

if data["failure_modes"]:
    st.subheader("Why the closures failed")
    st.table([{"failure mode": k, "count": v} for k, v in data["failure_modes"].items()])

st.subheader("Conversations")
outcomes = data["outcomes"]
modes = data["audited_failure_modes"]
choice = st.multiselect(
    "Outcome", sorted(set(outcomes.values())),
    default=[o for o in ("false_deflection", "partial") if o in outcomes.values()],
)

for cid in sorted(outcomes):
    if choice and outcomes[cid] not in choice:
        continue
    rec = records[cid]
    with st.expander(f"{cid} — {outcomes[cid]} — {modes.get(cid, '')}"):
        st.markdown(f"**Resident ({rec['channel']}):** {rec['ticket_text']}")
        st.markdown(f"**AI replied, then closed:** {rec['ai_response']}")
