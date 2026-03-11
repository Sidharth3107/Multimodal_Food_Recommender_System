---
title: Nutriguard FIS
colorFrom: red
colorTo: green
sdk: docker
app_port: 7860
short_description: Multimodal food safety, barcode, and healthier alternative recommender.
---
# Nutriguard

Nutriguard is an offline-first food safety and nutrition recommendation system built around three inputs:

- Food image
- Ingredient text
- Barcode / UPC / EAN

It answers the problem statement directly:

1. Determines whether a food item is safe for a user profile based on allergies, diet preferences, and custom avoid lists.
2. Recommends healthier alternatives from the local OpenFoodFacts dataset.
3. Produces a risk score that combines image-derived signals from the local ViT checkpoint with nutrition data from OpenFoodFacts.

## What makes this project stand out

- Confidence-aware multimodal reasoning: weak image predictions are corrected with ingredient-pattern inference instead of being trusted blindly.
- Offline-first design: the main demo path works from assets already in this repository.
- Profile-aware fallback recommendations: if an exact same-style alternative is not available, the system proposes adjacent healthier options that still respect the user profile.
- Explainable output: the report shows which source drove the decision and why.
- Visual deliverables: the project can generate polished HTML case reports and a multi-case showcase site.
- Responsive web experience: a local website wraps the full model pipeline in a presentation-ready interface.

## What is in this repo

- `main.ipynb`: original research and training notebook.
- `Food_Vision_Model/checkpoint-2400`: trained ViT food classifier checkpoint.
- `nutriguard/`: production-style analysis package added on top of the notebook work.
- `webapp/`: responsive website, static assets, and local HTTP server.
- `tests/`: unit tests covering profile logic, report generation, web smoke checks, and end-to-end barcode analysis.
- `examples/profile_alex.json`: example user profile.
- `examples/demo_cases.json`: curated showcase scenarios.
- `generate_showcase.py`: batch runner that creates a demo-ready HTML showcase.
- `run_webapp.py`: entrypoint for the local website.

## Architecture

- Vision layer: local Hugging Face ViT checkpoint predicts the food class and confidence.
- Structured data layer: local OpenFoodFacts TSV powers barcode lookup and nutrition retrieval.
- Profile engine: allergy detection, diet-rule evaluation, and custom avoid-list scanning.
- Style inference: ingredient-pattern heuristics recover likely dish type when the image model is uncertain.
- Risk engine: combines allergy severity, diet conflicts, nutrition metrics, and visual confidence into a single 0-100 score.
- Recommender: searches similar products in OpenFoodFacts and proposes profile-compatible, nutritionally better alternatives, with adjacent-style fallback suggestions.
- Reporting layer: generates HTML reports with charts for single analyses or batch case studies.
- Website layer: serves a responsive analysis studio with uploads, previews, live results, and showcase links.

## Key improvements over the original notebook

- Added real barcode support from the local dataset.
- Replaced a hard-coded nutrition score with live nutrition lookup from OpenFoodFacts.
- Added actual healthier-alternative recommendations.
- Added a reusable Python package and CLI instead of notebook-only execution.
- Added tests and fixture data for reproducible validation.
- Added profile canonicalization so allergy synonyms like `lactose` map correctly to `milk`.
- Added confidence-aware ingredient fallback so low-confidence image predictions do not derail the final recommendation.
- Added batch showcase generation for presentation-ready project output.
- Added a responsive local website for interactive use and demonstration.

## Usage

Run a barcode-first analysis:

```powershell
.\.venv\Scripts\python.exe .\main.py --profile .\examples\profile_alex.json --barcode 1001 --dataset .\tests\data\sample_openfoodfacts.tsv
```

Run an image + ingredients analysis with the full local dataset:

```powershell
.\.venv\Scripts\python.exe .\main.py --profile .\examples\profile_alex.json --image .\data\input_images\pizza.jpg --ingredients "Enriched flour, tomato puree, mozzarella cheese, pepperoni"
```

Render JSON output and save an HTML report:

```powershell
.\.venv\Scripts\python.exe .\main.py --profile .\examples\profile_alex.json --barcode 1001 --dataset .\tests\data\sample_openfoodfacts.tsv --html-report .\examples\single_report.html --save-json .\examples\single_report.json
```

Generate the full showcase site:

```powershell
.\.venv\Scripts\python.exe .\generate_showcase.py --cases .\examples\demo_cases.json --output-dir .\examples\showcase_output
```

Run the local website:

```powershell
.\.venv\Scripts\python.exe .\run_webapp.py --host 127.0.0.1 --port 8010
```

Then open `http://127.0.0.1:8010` in a browser.

## Validation

Run tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

## Current limitations

- The saved ViT checkpoint still has weak top-1 accuracy on some food photos, so the application intentionally treats low-confidence vision output as advisory rather than authoritative.
- Barcode quality and alternative quality depend on OpenFoodFacts completeness.
- The image model is trained on 60 classes present in the saved checkpoint, not the full Food-101 set.

