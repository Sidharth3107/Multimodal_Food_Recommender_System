# Project Review

## Original project assessment

Before the refactor, the repository only partially met the problem statement.

### What it already did well

- Fine-tuned a local ViT checkpoint for food image classification.
- Parsed ingredient text and detected common allergens.
- Combined image prediction and ingredient checks into a simple recommendation example.

### What was missing or incomplete

- No barcode workflow was implemented, even though the problem statement explicitly requires barcode input.
- No real healthier-alternative recommendation engine existed.
- The final notebook demo used a hard-coded nutrition score instead of product nutrition from the dataset.
- The system was notebook-only, which made it hard to demo, test, or reuse reliably.
- No automated tests or reproducible CLI existed.
- The ingredient NER path depended on a remote model and was not necessary for an offline demo.

## What has been added now

- A reusable `nutriguard` application package.
- Barcode lookup against OpenFoodFacts.
- Canonical allergy handling and richer diet rules including vegan, vegetarian, keto, gluten-free, dairy-free, low-sodium, and low-sugar.
- A weighted risk score combining image output, allergies, diet conflicts, and nutrition metrics.
- Confidence-aware ingredient fallback for low-confidence image predictions.
- Healthier alternative recommendations from similar products in the dataset, plus adjacent-style fallback suggestions.
- CLI entrypoint, sample profile, tests, and documentation.

## Bottom line

The original repository was a strong prototype but not a complete submission for the stated problem. The upgraded repository is now much closer to a complete and defendable project because it covers all required input modes and produces a structured recommendation with verifiable outputs and stronger fallback behavior when the image model is uncertain.
