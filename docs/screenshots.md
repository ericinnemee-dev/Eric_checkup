# Heatmap screenshot runbook

Dit document beschrijft hoe je een **deterministische screenshot** maakt van de capaciteit-heatmap.

## Doel
Een uniforme screenshot van de UI met een zichtbaar high-risk heatmap-cel (rode rand).

## Voorwaarden
- Backend draait lokaal op `http://127.0.0.1:8000`.
- Python met `playwright` package en Chromium browser geïnstalleerd.

## Eenmalige setup
```bash
pip install playwright
python -m playwright install chromium
```

## Screenshot maken (één command)
```bash
bash scripts/capture_heatmap.sh
```

## Output
De screenshot komt terecht in:
- `artifacts/heatmap-mvp.png`

## Optionele variabelen
- `BASE_URL` (default `http://127.0.0.1:8000`)
- `OUT` (default `artifacts/heatmap-mvp.png`)

Voorbeeld:
```bash
BASE_URL=http://localhost:9000 OUT=artifacts/my-shot.png bash scripts/capture_heatmap.sh
```
