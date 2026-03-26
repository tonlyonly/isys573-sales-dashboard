"""
ISYS 573 Sales Dashboard
========================
Reads data/sales.csv and generates an interactive HTML report with:
  - Quarter filter dropdown (Q1 / Q2 / Q3 / Q4 / Full Year)
  - Revenue by region (bar chart)
  - Monthly revenue trend (line chart)
  - Revenue by category (pie chart)
  - Top 10 products by revenue (horizontal bar)
  - Summary KPI cards

Usage:
    python dashboard.py                      # outputs dashboard.html
    python dashboard.py --output report.html # custom output path
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots


DATA_PATH = Path(__file__).parent / "data" / "sales.csv"


def load_data(path: Path = DATA_PATH) -> pd.DataFrame:
    """Load and validate the sales CSV."""
    if not path.exists():
        raise FileNotFoundError(f"Sales data not found: {path}")
    df = pd.read_csv(path, parse_dates=["date"])
    required = {"date", "region", "category", "product",
                "units_sold", "unit_price", "revenue", "channel"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    df["quarter"] = df["date"].dt.quarter.map(
        {1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}
    )
    df["month"] = df["date"].dt.to_period("M").astype(str)
    return df


def build_region_bar(df: pd.DataFrame) -> go.Figure:
    """Revenue by region — bar chart."""
    summary = (
        df.groupby("region")["revenue"]
        .sum()
        .reset_index()
        .sort_values("revenue", ascending=False)
    )
    colors = ["#00B4D8", "#F4A261", "#02C39A", "#9B59B6"]
    fig = go.Figure(go.Bar(
        x=summary["region"],
        y=summary["revenue"],
        marker_color=colors[:len(summary)],
        hovertemplate="<b>%{x}</b><br>Revenue: $%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        title="Revenue by Region",
        plot_bgcolor="white",
        yaxis=dict(tickprefix="$", tickformat=",.0f", title="Total Revenue ($)"),
        xaxis=dict(
            title="Region",
            categoryorder="array",
            categoryarray=summary["region"].tolist(),
        ),
        showlegend=False,
        margin=dict(t=50, b=30),
    )
    return fig


def build_monthly_line(df: pd.DataFrame) -> go.Figure:
    """Monthly revenue trend — line chart."""
    monthly = (
        df.groupby("month")["revenue"]
        .sum()
        .reset_index()
        .sort_values("month")
    )
    fig = px.line(
        monthly, x="month", y="revenue",
        markers=True,
        labels={"revenue": "Revenue ($)", "month": "Month"},
        title="Monthly Revenue Trend",
        color_discrete_sequence=["#2196F3"],
    )
    fig.update_layout(plot_bgcolor="white",
                      yaxis=dict(tickprefix="$", tickformat=",.0f"),
                      margin=dict(t=50, b=30))
    fig.update_traces(
        hovertemplate="<b>%{x}</b><br>Revenue: $%{y:,.0f}<extra></extra>",
        line=dict(width=2.5)
    )
    return fig


def build_category_pie(df: pd.DataFrame) -> go.Figure:
    """Revenue by product category — pie chart."""
    cat = df.groupby("category")["revenue"].sum().reset_index()
    fig = px.pie(
        cat, names="category", values="revenue",
        color_discrete_sequence=px.colors.qualitative.Pastel,
        title="Revenue by Category",
        hole=0.35,
    )
    fig.update_traces(
        textposition="inside", textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>Revenue: $%{value:,.0f}<br>Share: %{percent}<extra></extra>"
    )
    fig.update_layout(margin=dict(t=50, b=10))
    return fig


def build_top_products(df: pd.DataFrame, n: int = 10) -> go.Figure:
    """Top N products by revenue — horizontal bar chart."""
    top = (
        df.groupby("product")["revenue"]
        .sum()
        .nlargest(n)
        .reset_index()
        .sort_values("revenue")
    )
    fig = px.bar(
        top, x="revenue", y="product",
        orientation="h",
        color="revenue",
        color_continuous_scale="Blues",
        labels={"revenue": "Revenue ($)", "product": "Product"},
        title=f"Top {n} Products by Revenue",
    )
    fig.update_layout(
        coloraxis_showscale=False,
        plot_bgcolor="white",
        xaxis=dict(tickprefix="$", tickformat=",.0f"),
        margin=dict(t=50, b=30)
    )
    fig.update_traces(
        hovertemplate="<b>%{y}</b><br>Revenue: $%{x:,.0f}<extra></extra>"
    )
    return fig


def kpi_card_html(label: str, value: str, color: str = "#2196F3") -> str:
    """Render a single KPI card as HTML."""
    return f"""
    <div style="background:#fff;border-radius:8px;padding:20px 24px;
                box-shadow:0 2px 8px rgba(0,0,0,.08);text-align:center;
                border-top:4px solid {color};flex:1;min-width:160px;">
      <div style="font-size:13px;color:#666;font-weight:600;
                  text-transform:uppercase;letter-spacing:.5px;">{label}</div>
      <div style="font-size:28px;font-weight:700;color:#1a1a2e;margin-top:6px;">{value}</div>
    </div>"""


def build_html(df: pd.DataFrame) -> str:
    """
    Assemble the full dashboard HTML with quarter-filter dropdown.
    All charts are rendered as divs; JavaScript swaps the Plotly JSON
    when the user changes the dropdown selection.
    """
    quarters = ["Full Year", "Q1", "Q2", "Q3", "Q4"]
    chart_data: dict[str, dict] = {}

    for q in quarters:
        subset = df if q == "Full Year" else df[df["quarter"] == q]
        if subset.empty:
            # Placeholder for quarters with no data
            empty = go.Figure()
            empty.update_layout(title="No data for this period")
            chart_data[q] = {
                "region": empty.to_json(),
                "monthly": empty.to_json(),
                "category": empty.to_json(),
                "top_products": empty.to_json(),
                "total_revenue": "$0",
                "total_orders": "0",
                "avg_order": "$0",
                "top_region": "—",
            }
            continue

        total_rev = subset["revenue"].sum()
        total_orders = len(subset)
        avg_order = total_rev / total_orders if total_orders else 0
        top_region = (
            subset.groupby("region")["revenue"].sum().idxmax()
            if not subset.empty else "—"
        )

        chart_data[q] = {
            "region":       build_region_bar(subset).to_json(),
            "monthly":      build_monthly_line(subset).to_json(),
            "category":     build_category_pie(subset).to_json(),
            "top_products": build_top_products(subset).to_json(),
            "total_revenue": f"${total_rev:,.0f}",
            "total_orders":  f"{total_orders:,}",
            "avg_order":     f"${avg_order:,.0f}",
            "top_region":    top_region,
        }

    # Serialize all chart data to embed in HTML
    import json
    chart_json = json.dumps(chart_data)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>ISYS 573 · Retail Sales Dashboard</title>
  <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0;}}
    body{{font-family:'Segoe UI',Arial,sans-serif;background:#f4f6f9;color:#1a1a2e;}}
    header{{background:linear-gradient(135deg,#0D1B2A 0%,#1E3A5F 100%);
            color:#fff;padding:24px 32px;display:flex;
            align-items:center;justify-content:space-between;}}
    header h1{{font-size:22px;font-weight:700;}}
    header p{{font-size:13px;color:#8DA9C4;margin-top:4px;}}
    .filter-bar{{background:#fff;padding:14px 32px;
                 border-bottom:1px solid #e0e6ed;
                 display:flex;align-items:center;gap:16px;}}
    .filter-bar label{{font-size:14px;font-weight:600;color:#444;}}
    select{{padding:8px 14px;border:1.5px solid #cdd8e3;border-radius:6px;
            font-size:14px;background:#fff;cursor:pointer;color:#1a1a2e;}}
    select:focus{{outline:none;border-color:#2196F3;}}
    .kpis{{display:flex;gap:16px;flex-wrap:wrap;padding:24px 32px 8px;}}
    .charts-grid{{display:grid;
                  grid-template-columns:1fr 1fr;
                  gap:20px;padding:16px 32px 32px;}}
    .chart-card{{background:#fff;border-radius:10px;
                 padding:8px;box-shadow:0 2px 8px rgba(0,0,0,.06);}}
    @media(max-width:800px){{.charts-grid{{grid-template-columns:1fr;}}}}
    footer{{text-align:center;padding:16px;font-size:12px;color:#999;
            border-top:1px solid #e0e6ed;background:#fff;}}
  </style>
</head>
<body>

<header>
  <div>
    <h1>🛒 Retail Sales Dashboard</h1>
    <p>ISYS 573 · Generative AI and LLMs for Business · SFSU</p>
  </div>
  <div style="font-size:12px;color:#8DA9C4;text-align:right;">
    Data: 2024 Retail Sales<br>500 transactions · 4 regions · 6 categories
  </div>
</header>

<div class="filter-bar">
  <label for="qFilter">📅 Filter by Quarter:</label>
  <select id="qFilter" onchange="applyFilter(this.value)">
    {"".join(f'<option value="{q}">{q}</option>' for q in quarters)}
  </select>
  <span id="filterLabel" style="font-size:13px;color:#666;margin-left:8px;"></span>
</div>

<div class="kpis" id="kpiRow"></div>

<div class="charts-grid">
  <div class="chart-card"><div id="chartRegion"  style="height:340px;"></div></div>
  <div class="chart-card"><div id="chartMonthly" style="height:340px;"></div></div>
  <div class="chart-card"><div id="chartCategory"    style="height:340px;"></div></div>
  <div class="chart-card"><div id="chartTopProducts" style="height:340px;"></div></div>
</div>

<footer>
  Built with Python · Pandas · Plotly &nbsp;|&nbsp;
  ISYS 573 AugOps Demo &nbsp;|&nbsp;
  github.com/[your-handle]/isys573-sales-dashboard
</footer>

<script>
const DATA = {chart_json};

const KPI_COLORS = ["#2196F3","#4CAF50","#FF9800","#9C27B0"];
const KPI_LABELS = ["Total Revenue","Transactions","Avg Transaction","Top Region"];
const KPI_KEYS   = ["total_revenue","total_orders","avg_order","top_region"];

function applyFilter(quarter) {{
  const d = DATA[quarter];

  // KPI cards
  const kpiRow = document.getElementById("kpiRow");
  kpiRow.innerHTML = KPI_KEYS.map((k,i) => `
    <div style="background:#fff;border-radius:8px;padding:18px 22px;
                box-shadow:0 2px 8px rgba(0,0,0,.07);text-align:center;
                border-top:4px solid ${{KPI_COLORS[i]}};flex:1;min-width:150px;">
      <div style="font-size:12px;color:#888;font-weight:600;
                  text-transform:uppercase;letter-spacing:.4px;">${{KPI_LABELS[i]}}</div>
      <div style="font-size:26px;font-weight:700;color:#1a1a2e;margin-top:5px;">${{d[k]}}</div>
    </div>`).join("");

  // Charts
  Plotly.react("chartRegion",      JSON.parse(d.region).data,      JSON.parse(d.region).layout,      {{responsive:true}});
  Plotly.react("chartMonthly",     JSON.parse(d.monthly).data,     JSON.parse(d.monthly).layout,     {{responsive:true}});
  Plotly.react("chartCategory",    JSON.parse(d.category).data,    JSON.parse(d.category).layout,    {{responsive:true}});
  Plotly.react("chartTopProducts", JSON.parse(d.top_products).data, JSON.parse(d.top_products).layout, {{responsive:true}});

  document.getElementById("filterLabel").textContent =
    quarter === "Full Year" ? "Showing all 2024 data" : `Showing ${{quarter}} 2024 only`;
}}

// Initialise on load
applyFilter("Full Year");
</script>
</body>
</html>"""
    return html


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ISYS 573 Sales Dashboard")
    parser.add_argument("--data",   default=str(DATA_PATH), help="Path to sales CSV")
    parser.add_argument("--output", default="dashboard.html", help="Output HTML file")
    args = parser.parse_args()

    print(f"Loading data from {args.data} …")
    df = load_data(Path(args.data))
    print(f"  {len(df)} rows · {df['region'].nunique()} regions · "
          f"{df['category'].nunique()} categories")

    print("Building dashboard …")
    html = build_html(df)

    out = Path(args.output)
    out.write_text(html, encoding="utf-8")
    print(f"✅  Dashboard saved → {out.resolve()}")
    print(f"   Open in browser: file://{out.resolve()}")


if __name__ == "__main__":
    main()
