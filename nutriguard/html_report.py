from __future__ import annotations

import base64
import io
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from jinja2 import Template

from .models import AnalysisResult

REPORT_TEMPLATE = Template(
    """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }}</title>
  <style>
    :root {
      --bg: #f4efe7;
      --panel: #fffaf2;
      --ink: #1f2933;
      --muted: #55606d;
      --accent: #b04a2f;
      --good: #2d6a4f;
      --warn: #c77900;
      --bad: #a61b29;
      --line: #eadfce;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(176,74,47,0.16), transparent 32%),
        linear-gradient(180deg, #fbf7f1, var(--bg));
    }
    .wrap {
      max-width: 1180px;
      margin: 0 auto;
      padding: 40px 24px 64px;
    }
    .hero {
      background: linear-gradient(135deg, rgba(176,74,47,0.92), rgba(90,40,24,0.96));
      color: #fff8ef;
      border-radius: 24px;
      padding: 28px;
      box-shadow: 0 18px 48px rgba(59, 30, 18, 0.18);
    }
    .hero h1 {
      margin: 0 0 12px;
      font-size: clamp(32px, 5vw, 54px);
      line-height: 0.95;
      letter-spacing: -0.03em;
    }
    .hero p {
      margin: 0;
      font-size: 18px;
      max-width: 820px;
      color: rgba(255, 248, 239, 0.9);
    }
    .chips {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      margin-top: 18px;
    }
    .chip {
      padding: 10px 14px;
      border-radius: 999px;
      background: rgba(255,255,255,0.12);
      border: 1px solid rgba(255,255,255,0.14);
      font-size: 14px;
      letter-spacing: 0.02em;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(12, 1fr);
      gap: 18px;
      margin-top: 22px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 22px;
      box-shadow: 0 10px 24px rgba(87, 64, 40, 0.06);
    }
    .span-4 { grid-column: span 4; }
    .span-5 { grid-column: span 5; }
    .span-6 { grid-column: span 6; }
    .span-7 { grid-column: span 7; }
    .span-8 { grid-column: span 8; }
    .span-12 { grid-column: span 12; }
    h2 {
      margin: 0 0 16px;
      font-size: 18px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
    }
    .metric {
      display: flex;
      align-items: baseline;
      gap: 12px;
      margin-bottom: 16px;
    }
    .metric .value {
      font-size: clamp(42px, 5vw, 68px);
      line-height: 1;
      letter-spacing: -0.04em;
    }
    .metric .label { color: var(--muted); }
    .status {
      display: inline-block;
      padding: 8px 12px;
      border-radius: 999px;
      font-size: 13px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #fff;
    }
    .status.safe { background: var(--good); }
    .status.caution { background: var(--warn); }
    .status.avoid { background: var(--bad); }
    ul, ol { margin: 0; padding-left: 18px; }
    li { margin: 0 0 8px; }
    .muted { color: var(--muted); }
    .chart { width: 100%; border-radius: 16px; border: 1px solid var(--line); background: #fff; }
    .prediction-row, .alt-row {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      padding: 10px 0;
      border-top: 1px solid var(--line);
    }
    .prediction-row:first-child, .alt-row:first-child { border-top: 0; }
    .small { font-size: 14px; color: var(--muted); }
    .evidence {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .evidence div {
      padding: 12px;
      border-radius: 16px;
      background: #fff;
      border: 1px solid var(--line);
    }
    code {
      font-family: "Cascadia Mono", Consolas, monospace;
      font-size: 12px;
      color: #6f3424;
    }
    @media (max-width: 900px) {
      .span-4, .span-5, .span-6, .span-7, .span-8, .span-12 { grid-column: span 12; }
      .evidence { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1>{{ result.product_name }}</h1>
      <p>{{ result.summary }}</p>
      <div class="chips">
        <span class="chip">Risk score: {{ "%.1f"|format(result.risk_score) }}/100</span>
        <span class="chip">Safe to eat: {{ "Yes" if result.safe_to_eat else "No" }}</span>
        <span class="chip">Status: {{ result.status|upper }}</span>
      </div>
    </section>

    <section class="grid">
      <article class="panel span-4">
        <h2>Decision</h2>
        <div class="metric">
          <div class="value">{{ "%.1f"|format(result.risk_score) }}</div>
          <div class="label">risk score</div>
        </div>
        <div class="status {{ result.status }}">{{ result.status }}</div>
        <p class="muted" style="margin-top:16px;">{{ result.summary }}</p>
      </article>

      <article class="panel span-8">
        <h2>Risk Breakdown</h2>
        <img class="chart" alt="Risk breakdown chart" src="{{ risk_chart }}">
      </article>

      <article class="panel span-6">
        <h2>Warnings</h2>
        <ul>
        {% for item in result.warnings %}
          <li>{{ item }}</li>
        {% else %}
          <li>No blocking warnings detected.</li>
        {% endfor %}
        </ul>
      </article>

      <article class="panel span-6">
        <h2>Health Notes</h2>
        <ul>
        {% for item in result.health_notes %}
          <li>{{ item }}</li>
        {% else %}
          <li>No additional health notes.</li>
        {% endfor %}
        </ul>
      </article>

      <article class="panel span-5">
        <h2>Image Evidence</h2>
        <img class="chart" alt="Top image predictions" src="{{ prediction_chart }}">
        {% if result.image_prediction %}
        <div style="margin-top: 14px;">
          {% for entry in result.image_prediction.top_k %}
            <div class="prediction-row">
              <div>{{ entry.label }}</div>
              <div class="small">{{ "%.1f"|format(entry.confidence * 100) }}%</div>
            </div>
          {% endfor %}
        </div>
        {% else %}
        <p class="muted">No image supplied.</p>
        {% endif %}
      </article>

      <article class="panel span-7">
        <h2>Alternatives</h2>
        {% for alt in result.healthier_alternatives %}
          <div class="alt-row">
            <div>
              <strong>{{ alt.product_name }}</strong><br>
              <span class="small">{{ alt.main_category or "Unknown category" }}</span><br>
              <span class="small">{{ alt.reason }}</span>
            </div>
            <div class="small">Score {{ "%.1f"|format(alt.nutrition_score) if alt.nutrition_score is not none else "n/a" }}</div>
          </div>
        {% else %}
          <p class="muted">No profile-compatible alternatives found in the current search scope.</p>
        {% endfor %}
      </article>

      <article class="panel span-12">
        <h2>Evidence Snapshot</h2>
        <div class="evidence">
          <div>
            <strong>Detected allergens</strong><br>
            <span class="small">{{ result.detected_allergens|join(', ') if result.detected_allergens else 'None' }}</span>
          </div>
          <div>
            <strong>Trace allergens</strong><br>
            <span class="small">{{ result.trace_allergens|join(', ') if result.trace_allergens else 'None' }}</span>
          </div>
          <div>
            <strong>Likely allergens</strong><br>
            <span class="small">{{ result.probable_allergens|join(', ') if result.probable_allergens else 'None' }}</span>
          </div>
          <div>
            <strong>Diet conflicts</strong><br>
            <span class="small">{{ result.diet_conflicts|join(' | ') if result.diet_conflicts else 'None' }}</span>
          </div>
          <div>
            <strong>Parsed ingredients</strong><br>
            <span class="small">{{ result.parsed_ingredients[:12]|join(', ') if result.parsed_ingredients else 'Not provided' }}</span>
          </div>
        </div>
      </article>
    </section>
  </div>
</body>
</html>
    """
)

INDEX_TEMPLATE = Template(
    """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }}</title>
  <style>
    body {
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background: linear-gradient(180deg, #f8f2ea, #efe6db);
      color: #1f2933;
    }
    .wrap { max-width: 1180px; margin: 0 auto; padding: 40px 24px 64px; }
    .hero {
      background: linear-gradient(135deg, #22333b, #3d5a63);
      color: #fff;
      border-radius: 24px;
      padding: 30px;
      box-shadow: 0 18px 48px rgba(34, 51, 59, 0.18);
    }
    .hero h1 { margin: 0 0 10px; font-size: clamp(32px, 5vw, 56px); letter-spacing: -0.04em; }
    .hero p { margin: 0; max-width: 760px; color: rgba(255,255,255,0.85); }
    .grid {
      margin-top: 22px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 18px;
    }
    .card {
      display: block;
      text-decoration: none;
      color: inherit;
      padding: 22px;
      border-radius: 22px;
      background: rgba(255,255,255,0.82);
      border: 1px solid rgba(46, 64, 73, 0.08);
      box-shadow: 0 10px 24px rgba(66, 52, 39, 0.06);
    }
    .status {
      display: inline-block;
      padding: 6px 10px;
      border-radius: 999px;
      color: white;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    .safe { background: #2d6a4f; }
    .caution { background: #c77900; }
    .avoid { background: #a61b29; }
    .score { font-size: 42px; margin: 14px 0 6px; letter-spacing: -0.05em; }
    .small { color: #55606d; font-size: 14px; }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1>{{ title }}</h1>
      <p>{{ subtitle }}</p>
    </section>
    <section class="grid">
      {% for item in items %}
      <a class="card" href="{{ item.href }}">
        <span class="status {{ item.status }}">{{ item.status }}</span>
        <div class="score">{{ "%.1f"|format(item.risk_score) }}</div>
        <strong>{{ item.title }}</strong>
        <p class="small">{{ item.summary }}</p>
      </a>
      {% endfor %}
    </section>
  </div>
</body>
</html>
    """
)


def _fig_to_data_uri(fig) -> str:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=160, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    payload = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{payload}"


def _build_risk_chart(result: AnalysisResult) -> str:
    labels = ["Allergy", "Diet", "Nutrition", "Vision"]
    values = [
        result.risk_breakdown.allergy_component,
        result.risk_breakdown.diet_component,
        result.risk_breakdown.nutrition_component,
        result.risk_breakdown.vision_component,
    ]
    colors = ["#a61b29", "#c77900", "#356f5a", "#3d5a63"]
    fig, ax = plt.subplots(figsize=(7.2, 4.2), facecolor="#fffaf2")
    ax.barh(labels, values, color=colors)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Component score")
    ax.set_title("Risk components")
    for index, value in enumerate(values):
        ax.text(value + 1.5, index, f"{value:.1f}", va="center", fontsize=10)
    fig.tight_layout()
    return _fig_to_data_uri(fig)


def _build_prediction_chart(result: AnalysisResult) -> str:
    fig, ax = plt.subplots(figsize=(7.2, 4.2), facecolor="#fffaf2")
    if result.image_prediction and result.image_prediction.top_k:
        labels = [entry["label"] for entry in result.image_prediction.top_k]
        values = [float(entry["confidence"]) * 100.0 for entry in result.image_prediction.top_k]
        ax.barh(labels[::-1], values[::-1], color="#b04a2f")
        ax.set_xlim(0, max(40.0, max(values) + 5.0))
        ax.set_xlabel("Confidence (%)")
        ax.set_title("Top image predictions")
    else:
        ax.text(0.5, 0.5, "No image supplied", ha="center", va="center", fontsize=14)
        ax.axis("off")
    fig.tight_layout()
    return _fig_to_data_uri(fig)


def render_html_report(result: AnalysisResult, title: str | None = None) -> str:
    return REPORT_TEMPLATE.render(
        title=title or result.product_name,
        result=result,
        risk_chart=_build_risk_chart(result),
        prediction_chart=_build_prediction_chart(result),
    )


def save_html_report(result: AnalysisResult, output_path: str | Path, title: str | None = None) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_html_report(result, title=title), encoding="utf-8")
    return output


def render_showcase_index(items: list[dict[str, object]], title: str, subtitle: str) -> str:
    return INDEX_TEMPLATE.render(items=items, title=title, subtitle=subtitle)


def save_showcase_index(items: list[dict[str, object]], output_path: str | Path, title: str, subtitle: str) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_showcase_index(items, title=title, subtitle=subtitle), encoding="utf-8")
    return output

