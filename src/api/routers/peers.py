from __future__ import annotations
import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from api.db import get_connection

router = APIRouter(tags=["peers"])

RADAR_AXES = {
    "ROE": "return_on_equity_pct", "ROCE": "return_on_capital_employed_pct",
    "NPM": "net_profit_margin_pct", "D/E": "debt_to_equity",
    "FCF": "free_cash_flow_cr", "PAT CAGR 5yr": "pat_cagr_5yr",
    "Revenue CAGR 5yr": "revenue_cagr_5yr", "Composite Score": "composite_quality_score",
}


@router.get("/peers/{group_name}")
def get_peer_group(group_name: str):
    """All companies in a peer group with percentile rank for each of 10 metrics. 404 for unknown group."""
    conn = get_connection()
    exists = conn.execute("SELECT 1 FROM peer_groups WHERE peer_group_name = ?", (group_name,)).fetchone()
    if not exists:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Peer group '{group_name}' not found")

    rows = conn.execute("""
        SELECT company_id, metric, value, percentile_rank FROM peer_percentiles
        WHERE peer_group_name = ?
    """, (group_name,)).fetchall()
    conn.close()

    by_company = {}
    for r in rows:
        by_company.setdefault(r["company_id"], {})[r["metric"]] = {
            "value": r["value"], "percentile_rank": r["percentile_rank"]
        }
    return {"peer_group_name": group_name, "count": len(by_company), "companies": by_company}


@router.get("/companies/{ticker}/peers/compare")
def compare_to_peers(ticker: str):
    """Radar data: 8 axis metrics for the company + peer group average + benchmark company."""
    conn = get_connection()
    ticker = ticker.strip().upper()
    if not conn.execute("SELECT 1 FROM companies WHERE id = ?", (ticker,)).fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail=f"Company '{ticker}' not found")

    group_row = conn.execute("SELECT peer_group_name FROM peer_groups WHERE company_id = ?", (ticker,)).fetchone()
    if not group_row:
        conn.close()
        return {"company_id": ticker, "peer_group": None, "message": "No peer group assigned"}

    group_name = group_row["peer_group_name"]
    benchmark_row = conn.execute(
        "SELECT company_id FROM peer_groups WHERE peer_group_name = ? AND is_benchmark = 1", (group_name,)
    ).fetchone()
    benchmark = benchmark_row["company_id"] if benchmark_row else None

    latest = conn.execute("""
        SELECT * FROM financial_ratios f1 WHERE company_id = ?
        AND net_profit_margin_pct IS NOT NULL
        AND year = (SELECT MAX(f2.year) FROM financial_ratios f2
                    WHERE f2.company_id = f1.company_id AND f2.net_profit_margin_pct IS NOT NULL)
    """, (ticker,)).fetchone()

    company_axes = {label: latest[col] for label, col in RADAR_AXES.items()} if latest else {}

    group_members = [r["company_id"] for r in conn.execute(
        "SELECT company_id FROM peer_groups WHERE peer_group_name = ?", (group_name,)
    ).fetchall()]
    avg_axes = {}
    for label, col in RADAR_AXES.items():
        placeholders = ",".join("?" * len(group_members))
        vals = [r[0] for r in conn.execute(
            f"""SELECT f1.{col} FROM financial_ratios f1 WHERE company_id IN ({placeholders})
                AND net_profit_margin_pct IS NOT NULL
                AND year = (SELECT MAX(f2.year) FROM financial_ratios f2
                            WHERE f2.company_id = f1.company_id AND f2.net_profit_margin_pct IS NOT NULL)""",
            group_members,
        ).fetchall() if r[0] is not None]
        avg_axes[label] = round(sum(vals) / len(vals), 2) if vals else None

    conn.close()
    return {
        "company_id": ticker, "peer_group": group_name, "benchmark": benchmark,
        "company_values": company_axes, "peer_group_average": avg_axes,
    }