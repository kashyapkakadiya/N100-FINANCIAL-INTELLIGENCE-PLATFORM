"""
src/analytics/clustering.py — Module 10, Day 36: KMeans Clustering.

Features: return_on_equity_pct, debt_to_equity, revenue_cagr_5yr,
fcf_cagr_5yr, operating_profit_margin_pct. Missing values imputed with
sector median before scaling (per spec), then StandardScaler, then
KMeans(n_clusters=5, random_state=42).

FLAGGED FINDING: fcf_cagr_5yr is missing for 44/92 companies (48%) - a
CAGR edge case (insufficient history, turnaround, zero-base - see Sprint 2's
compute_cagr_for_window). Sector-median imputation on nearly half the
dataset for one of five features is a real signal-dilution risk worth
knowing about before treating cluster assignments as fully reliable -
documented in the printed summary, not silently accepted.
"""
from __future__ import annotations
import sys
import sqlite3
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analytics.cagr import compute_cagr_for_window

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "nifty100.db"
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output"
REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports"

FEATURES = ["return_on_equity_pct", "debt_to_equity", "revenue_cagr_5yr",
            "fcf_cagr_5yr", "operating_profit_margin_pct"]

CLUSTER_NAMES = {
    0: "Elite Return Compounders",
    1: "Stable Core Holdings",
    2: "Leveraged Growth",
    3: "Quality Growth, Low Leverage",
    4: "Asset-Light / High-Margin",
}


def load_clustering_data(conn) -> pd.DataFrame:
    ratios = pd.read_sql("""
        SELECT f.company_id, f.return_on_equity_pct, f.debt_to_equity,
               f.revenue_cagr_5yr, f.operating_profit_margin_pct, s.broad_sector
        FROM financial_ratios f
        LEFT JOIN sectors s ON f.company_id = s.company_id
        WHERE f.net_profit_margin_pct IS NOT NULL
        AND f.year = (SELECT MAX(year) FROM financial_ratios f2
                      WHERE f2.company_id = f.company_id AND f2.net_profit_margin_pct IS NOT NULL)
    """, conn)

    # fcf_cagr_5yr isn't stored in financial_ratios (Sprint 2 only kept
    # revenue/PAT/EPS CAGR) - computed fresh here, same as Sprint 5.
    cf = pd.read_sql("SELECT company_id, year, operating_activity, investing_activity FROM cashflow", conn)
    cf["fcf"] = cf["operating_activity"] + cf["investing_activity"]
    fcf_cagr_rows = []
    for cid, g in cf.groupby("company_id"):
        series = g.sort_values("year").set_index("year")["fcf"].dropna().to_dict()
        cagr, _ = compute_cagr_for_window(series, 5)
        fcf_cagr_rows.append({"company_id": cid, "fcf_cagr_5yr": cagr})
    fcf_df = pd.DataFrame(fcf_cagr_rows)

    df = ratios.merge(fcf_df, on="company_id", how="left")
    return df


def impute_with_sector_median(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (imputed_df, imputation_log) - log records exactly which
    company/feature values were filled in, for transparency."""
    df = df.copy()
    log_rows = []
    for feature in FEATURES:
        sector_medians = df.groupby("broad_sector")[feature].median()
        overall_median = df[feature].median()
        for idx, row in df[df[feature].isna()].iterrows():
            sector_med = sector_medians.get(row["broad_sector"])
            fill_value = sector_med if pd.notna(sector_med) else overall_median
            df.at[idx, feature] = fill_value
            log_rows.append({
                "company_id": row["company_id"], "feature": feature,
                "sector": row["broad_sector"], "imputed_value": round(fill_value, 3),
            })
    return df, pd.DataFrame(log_rows)


def winsorize_features(df: pd.DataFrame, lower_q=0.05, upper_q=0.95) -> pd.DataFrame:
    """
    Clip each feature at P5/P95 before scaling. Not in the spec's literal
    instructions, but added after testing showed it's necessary: without
    it, BEL and HAL (ROE 3800-4700%, the same extreme-capital-structure
    anomalies documented in Sprint 2's ratio_edge_cases.log) form their own
    2-company cluster, and CIPLA (FCF CAGR 228% off a near-zero Rs 3 Cr
    base year - a near-zero-base CAGR distortion) becomes a 1-company
    cluster - using 2 of the 5 mandated cluster slots to quarantine known
    outliers rather than represent real business archetypes. With
    winsorization, cluster sizes go from [60,15,14,2,1] to a genuinely
    usable [10,34,15,22,11]. Same principle already applied to the
    composite quality score in Sprint 3.
    """
    df = df.copy()
    for feature in FEATURES:
        lo, hi = df[feature].quantile(lower_q), df[feature].quantile(upper_q)
        df[feature] = df[feature].clip(lower=lo, upper=hi)
    return df


def run_elbow_analysis(X_scaled: np.ndarray, k_range=range(2, 11)):
    inertias = []
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        km.fit(X_scaled)
        inertias.append(km.inertia_)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(list(k_range), inertias, marker="o")
    ax.axvline(x=5, color="red", linestyle="--", alpha=0.6, label="k=5 (chosen)")
    ax.set_xlabel("Number of clusters (k)")
    ax.set_ylabel("Inertia (within-cluster sum of squares)")
    ax.set_title("Elbow Plot — KMeans Inertia vs k")
    ax.legend()
    fig.tight_layout()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(REPORTS_DIR / "elbow_plot.png", dpi=150)
    plt.close(fig)
    return dict(zip(k_range, inertias))


def run_clustering():
    conn = sqlite3.connect(DB_PATH)
    df = load_clustering_data(conn)
    conn.close()

    missing_counts = df[FEATURES].isna().sum()
    print("Missing value counts per feature (before imputation):")
    print(missing_counts.to_string())
    print()

    imputed_df, imputation_log = impute_with_sector_median(df)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    imputation_log.to_csv(OUTPUT_DIR / "clustering_imputation_log.csv", index=False)

    winsorized_df = winsorize_features(imputed_df)

    X = winsorized_df[FEATURES].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    inertias = run_elbow_analysis(X_scaled)

    kmeans = KMeans(n_clusters=5, random_state=42, n_init=10)
    cluster_ids = kmeans.fit_predict(X_scaled)
    distances = kmeans.transform(X_scaled)
    distance_from_centroid = [distances[i, c] for i, c in enumerate(cluster_ids)]

    imputed_df["cluster_id"] = cluster_ids
    imputed_df["distance_from_centroid"] = np.round(distance_from_centroid, 4)

    return imputed_df, kmeans, scaler, inertias, missing_counts


if __name__ == "__main__":
    result_df, kmeans, scaler, inertias, missing_counts = run_clustering()

    print("Inertia by k (2-10):")
    for k, inertia in inertias.items():
        marker = " <-- chosen k" if k == 5 else ""
        print(f"  k={k}: {inertia:.1f}{marker}")
    print()

    print("Cluster sizes:")
    print(result_df["cluster_id"].value_counts().sort_index())
    print()

    # cluster_name assignment happens in Day 37 (profiling) - placeholder here
    result_df["cluster_name"] = result_df["cluster_id"].map(CLUSTER_NAMES)
    out_cols = ["company_id", "cluster_id", "cluster_name", "distance_from_centroid"]
    result_df[out_cols].to_csv(OUTPUT_DIR / "cluster_labels.csv", index=False)
    print(f"cluster_labels.csv written: {len(result_df)} companies")

    if len(missing_counts[missing_counts > 0]):
        print()
        print("NOTE: features with imputed values (see clustering_imputation_log.csv):")
        print(missing_counts[missing_counts > 0].to_string())