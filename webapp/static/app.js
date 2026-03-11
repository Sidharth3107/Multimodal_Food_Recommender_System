const SAMPLE_CASES = {
  vegan_pizza: {
    profile: {
      name: "Alex",
      diet: "vegan",
      allergies: "milk",
      avoid: "gelatin",
    },
    barcode: "",
    imagePath: "data/input_images/pizza.jpg",
    ingredients: "Enriched flour (wheat flour, niacin), tomato puree, mozzarella cheese (milk), pepperoni",
    dataset: "data/raw/en.openfoodfacts.org.products.tsv",
  },
  safe_salad: {
    profile: {
      name: "Alex",
      diet: "vegan",
      allergies: "milk",
      avoid: "gelatin",
    },
    barcode: "1003",
    imagePath: "",
    ingredients: "",
    dataset: "tests/data/sample_openfoodfacts.tsv",
  },
  keto_mix: {
    profile: {
      name: "Riya",
      diet: "keto",
      allergies: "",
      avoid: "",
    },
    barcode: "1004",
    imagePath: "",
    ingredients: "",
    dataset: "tests/data/sample_openfoodfacts.tsv",
  },
};

const form = document.getElementById("analysis-form");
const imageFileInput = document.getElementById("image-file");
const imagePreviewWrap = document.getElementById("image-preview-wrap");
const imagePreview = document.getElementById("image-preview");
const resultShell = document.getElementById("result-shell");
const formStatus = document.getElementById("form-status");
const analyzeButton = document.getElementById("analyze-button");
const showcaseGrid = document.getElementById("showcase-grid");
const showcaseCardTemplate = document.getElementById("showcase-card-template");

let imagePayload = null;

function splitList(value) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function setStatus(message) {
  formStatus.textContent = message;
}

function statusClass(status) {
  return `status-${status || "safe"}`;
}

function riskColor(score) {
  if (score >= 75) return "var(--berry)";
  if (score >= 50) return "var(--mustard)";
  return "var(--moss)";
}

function previewImage(dataUrl) {
  imagePreview.src = dataUrl;
  imagePreviewWrap.classList.remove("hidden");
}

function clearPreview() {
  imagePayload = null;
  imageFileInput.value = "";
  imagePreviewWrap.classList.add("hidden");
  imagePreview.removeAttribute("src");
}

imageFileInput.addEventListener("change", (event) => {
  const [file] = event.target.files || [];
  if (!file) {
    clearPreview();
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    imagePayload = {
      name: file.name,
      dataUrl: reader.result,
    };
    previewImage(reader.result);
    setStatus(`Loaded image: ${file.name}`);
  };
  reader.readAsDataURL(file);
});

for (const chip of document.querySelectorAll(".sample-chip")) {
  chip.addEventListener("click", () => {
    const sample = SAMPLE_CASES[chip.dataset.sample];
    if (!sample) return;
    document.getElementById("profile-name").value = sample.profile.name;
    document.getElementById("profile-diet").value = sample.profile.diet;
    document.getElementById("profile-allergies").value = sample.profile.allergies;
    document.getElementById("profile-avoid").value = sample.profile.avoid;
    document.getElementById("barcode").value = sample.barcode;
    document.getElementById("image-path").value = sample.imagePath;
    document.getElementById("ingredients-text").value = sample.ingredients;
    document.getElementById("dataset-path").value = sample.dataset;
    clearPreview();
    setStatus(`Loaded sample: ${chip.textContent}`);
  });
}

function renderTokens(items) {
  if (!items || !items.length) return `<div class="muted">None</div>`;
  return `<div class="inline-chip">${items.map((item) => `<span class="token">${item}</span>`).join("")}</div>`;
}

function renderList(items, emptyText) {
  if (!items || !items.length) return `<div class="muted">${emptyText}</div>`;
  return `<div class="stack-list">${items.map((item) => `<div>${item}</div>`).join("")}</div>`;
}

function renderBarList(entries, formatter) {
  if (!entries || !entries.length) return `<div class="muted">Not available</div>`;
  return `<div class="bar-list">${entries.map((entry) => {
    const label = entry.label ?? entry[0];
    const confidence = Number(entry.confidence ?? entry[1] ?? 0);
    const value = formatter(confidence);
    return `
      <div class="bar-row">
        <div class="bar-head"><span>${label}</span><span>${value}</span></div>
        <div class="bar-track"><div class="bar-fill" style="width:${Math.min(100, confidence * 100)}%"></div></div>
      </div>
    `;
  }).join("")}</div>`;
}

function renderAlternatives(items) {
  if (!items || !items.length) {
    return `<div class="muted">No profile-compatible alternatives were found in the current search scope.</div>`;
  }
  return items.map((item) => `
    <div class="alt-card">
      <strong>${item.product_name}</strong>
      <div class="alt-meta">${item.main_category || "Unknown category"}</div>
      <div class="alt-meta">Nutrition score: ${item.nutrition_score == null ? "n/a" : Number(item.nutrition_score).toFixed(1)}</div>
      <p>${item.reason}</p>
    </div>
  `).join("");
}

function renderResult(payload) {
  const result = payload.result;
  const score = Number(result.risk_score || 0);
  const gaugeFill = `${Math.min(100, score)}%`;
  const color = riskColor(score);
  const predictions = result.image_prediction ? result.image_prediction.top_k : [];
  const riskEntries = [
    { label: "Allergy", confidence: result.risk_breakdown.allergy_component / 100 },
    { label: "Diet", confidence: result.risk_breakdown.diet_component / 100 },
    { label: "Nutrition", confidence: result.risk_breakdown.nutrition_component / 100 },
    { label: "Vision", confidence: result.risk_breakdown.vision_component / 100 },
  ];

  resultShell.innerHTML = `
    <div class="result-layout">
      <div class="result-top">
        <div class="gauge-wrap">
          <div class="gauge" style="--gauge-fill:${gaugeFill}; background: conic-gradient(${color} ${score * 3.6}deg, rgba(27,43,47,0.08) 0deg);">
            <div class="gauge-value">
              <div class="gauge-number">${score.toFixed(1)}</div>
              <div class="gauge-label">risk score</div>
            </div>
          </div>
          <span class="result-status ${statusClass(result.status)}">${result.status}</span>
        </div>
        <div class="result-summary">
          <p class="eyebrow">Resolved product</p>
          <h3>${result.product_name}</h3>
          <p>${result.summary}</p>
          <div class="result-links">
            <a class="result-link" href="${payload.report_href}" target="_blank" rel="noreferrer">Open HTML report</a>
            <a class="result-link" href="${payload.json_href}" target="_blank" rel="noreferrer">Open JSON</a>
          </div>
        </div>
      </div>

      <div class="result-grid">
        <section class="result-card">
          <h4>Warnings</h4>
          ${renderList(result.warnings, "No blocking warnings detected.")}
        </section>

        <section class="result-card">
          <h4>Health notes</h4>
          ${renderList(result.health_notes, "No additional health notes.")}
        </section>

        <section class="result-card">
          <h4>Profile evidence</h4>
          <div class="stack-list">
            <div><strong>Detected allergens</strong>${renderTokens(result.detected_allergens)}</div>
            <div><strong>Trace allergens</strong>${renderTokens(result.trace_allergens)}</div>
            <div><strong>Likely allergens</strong>${renderTokens(result.probable_allergens)}</div>
            <div><strong>Diet conflicts</strong>${renderList(result.diet_conflicts, "None")}</div>
          </div>
        </section>

        <section class="result-card">
          <h4>Ingredients</h4>
          ${renderTokens(result.parsed_ingredients)}
        </section>

        <section class="result-card">
          <h4>Risk components</h4>
          ${renderBarList(riskEntries, (value) => `${(value * 100).toFixed(1)}`)}
        </section>

        <section class="result-card">
          <h4>Image confidence</h4>
          ${renderBarList(predictions, (value) => `${(value * 100).toFixed(1)}%`)}
        </section>

        <section class="result-card" style="grid-column:1 / -1;">
          <h4>Healthier alternatives</h4>
          ${renderAlternatives(result.healthier_alternatives)}
        </section>
      </div>
    </div>
  `;
}

async function loadShowcase() {
  try {
    const response = await fetch("/api/showcase");
    const payload = await response.json();
    showcaseGrid.innerHTML = "";
    for (const item of payload.cases || []) {
      const node = showcaseCardTemplate.content.firstElementChild.cloneNode(true);
      node.href = item.href;
      node.querySelector(".showcase-status").textContent = item.status;
      node.querySelector(".showcase-status").classList.add(statusClass(item.status));
      node.querySelector(".showcase-score").textContent = Number(item.risk_score).toFixed(1);
      node.querySelector("h3").textContent = item.title;
      node.querySelector("p").textContent = item.summary;
      showcaseGrid.appendChild(node);
    }
  } catch (error) {
    showcaseGrid.innerHTML = `<div class="muted">Could not load showcase cases.</div>`;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  analyzeButton.disabled = true;
  setStatus("Running analysis...");

  const payload = {
    profile: {
      name: document.getElementById("profile-name").value.trim() || "User",
      diet: document.getElementById("profile-diet").value || null,
      allergies: splitList(document.getElementById("profile-allergies").value),
      avoid_ingredients: splitList(document.getElementById("profile-avoid").value),
      strict_mode: true,
      health_goals: [],
    },
    barcode: document.getElementById("barcode").value.trim() || null,
    image_path: document.getElementById("image-path").value.trim() || null,
    ingredients_text: document.getElementById("ingredients-text").value.trim() || null,
    dataset: document.getElementById("dataset-path").value.trim() || null,
    checkpoint: document.getElementById("checkpoint-path").value.trim() || null,
  };

  if (imagePayload) {
    payload.image_b64 = imagePayload.dataUrl;
    payload.image_name = imagePayload.name;
  }

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || "Analysis failed");
    }
    renderResult(result);
    setStatus("Analysis complete.");
  } catch (error) {
    resultShell.innerHTML = `
      <div class="panel-head">
        <p class="eyebrow">Live output</p>
        <h2>Analysis failed</h2>
      </div>
      <p class="placeholder-copy">${error.message}</p>
    `;
    setStatus("Analysis failed.");
  } finally {
    analyzeButton.disabled = false;
  }
});

loadShowcase();

