# Deployment Guide

## Best free public hosting path

For this project, the best zero-hosting-cost path is a Docker-based Hugging Face Space.

Why this is the best fit:
- The app is a Python web server, not a static site.
- The repository includes local ML assets and a Torch/Transformers runtime.
- Hugging Face Spaces supports Docker and provides a free CPU tier that is better aligned with ML demos than a basic static host.

## Free URL you can get

If your Hugging Face username is `sid` and the Space name is `nutriguardfis`, the public app URL will be:

- `https://sid-nutriguardfis.hf.space`

## What is not free

`nutriguardfis.com` is not a zero-cost domain path unless you already own that domain.

Why:
- A `.com` domain must be registered through a domain registrar.
- Hugging Face custom domains are not on the free plan.
- Render supports custom domains, but you still need to own the domain itself.

## Repo preparation already completed

This repo is already prepared for the Space flow:
- `Dockerfile`
- `.dockerignore`
- Hugging Face Space metadata in `README.md`
- environment-aware host and port binding in `webapp/server.py`
- deployment-friendly dataset fallback via `data/deploy_openfoodfacts.tsv`
- `prepare_space_bundle.py` to export a slim upload bundle

## Recommended upload path

Run:

```powershell
.\.venv\Scripts\python.exe .\prepare_space_bundle.py
```

That creates:

- `deploy/hf_space_bundle`

The bundle excludes the 1 GB raw dataset and extra training checkpoints, while keeping the production checkpoint and the deployment dataset needed for the demo app.

## Hugging Face Space steps

1. Create a new Hugging Face Space.
2. Choose `Docker` as the SDK.
3. Name the Space `nutriguardfis`.
4. Upload or push the contents of `deploy/hf_space_bundle`.
5. Hugging Face will build the `Dockerfile` automatically.
6. The app will start on port `7860`.

## Domain note for `nutriguardfis.com`

If you already own `nutriguardfis.com`, I can help you point a paid-domain setup to the deployed app.
If you do not own it yet, the zero-cost public version should use the Hugging Face subdomain instead.
