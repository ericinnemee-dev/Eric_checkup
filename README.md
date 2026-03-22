# Eric Checkup – HMS Planning Kickstart

Dit project bevat nu een FastAPI backend met persistente opslag, migraties, auth + rollen en een eerste plannerflow.

## Wat staat er nu

- `backend/app/main.py`
  - health endpoint geeft ook de API-versie, environment en server UTC-timestamp terug.
  - capaciteit heatmap endpoint: `GET /capacity/heatmap` (MVP: hourly buckets, team/site scope, overlap-markering afwezigheid + onderbezetting).
  - Auth endpoint:
    - `POST /auth/token`
    - `GET /auth/me`
  - Planner endpoints:
    - `GET /health`
    - `POST /optimize` (planner, payload-driven, inclusief `score_breakdown`)
    - `POST /optimize/run` (planner, DB-driven + filters op IDs, team/site en tijdvenster + `score_breakdown`)
    - `POST /feedback` (planner)
    - `GET /kpis` (planner/viewer, optioneel filterbaar met `team_id`/`site_id`)
    - `GET /runs` (planner/viewer, recente optimizer runs met score-breakdown velden, filterbaar op scope + `limit`/`offset`)
    - `DELETE /runs/{run_id}` (planner, run + bijbehorende events verwijderen)
  - `optimizer_runs` slaat nu ook score-breakdown componenten op (`fill_rate`, `fairness`, `cost_score`, `route_score`, `penalty`).
  - CRUD endpoints:
    - `POST/GET/PATCH/DELETE /employees`
    - `POST/GET/PATCH/DELETE /shifts`
  - `employees` en `shifts` ondersteunen nu `team_id`, `site_id`, `cost_per_shift` (employee) en `route_distance_km` (shift).
  - auth middleware geeft nu expliciet `401` bij ontbrekende token in plaats van een impliciete bearer-fout.
  - input-validatie dwingt non-negatieve `cost_per_shift` en `route_distance_km` af.
  - list endpoints ondersteunen nu query filters + pagination (`team_id`, `site_id`, `required_skill`, `sort_by`, `sort_dir`, `limit`, `offset`).
- `backend/app/models.py`
  - SQLAlchemy modellen voor `users`, `employees`, `shifts`, `optimizer_runs`, `assignment_events`.
- `backend/alembic`
  - Alembic migrations (`0001` core tables + `0002` users table + `0003` team/site scope columns + `0004` run scope columns + `0005` employee cost + `0006` shift route distance + `0007` run score breakdown columns).
- `backend/tests`
  - planner unit tests
  - API contract tests (auth + CRUD + optimize/feedback/kpi flow)
  - planner ondersteunt gewogen scoring met constraints: `weight_fill_rate`, `weight_fairness`, `weight_cost`, `cost_normalizer`, `weight_route`, `route_normalizer`.

## Configuratie

De backend gebruikt settings uit environment (via `app/settings.py`).

Belangrijk:

```bash
export APP_ENV="dev"               # of production
export DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/hms"
export JWT_SECRET="vervang-dit-in-productie"
export JWT_ALG="HS256"
export JWT_TTL_MIN=60
export SEED_DEV_USERS=true          # zet false buiten local dev
```

Als je `APP_ENV=production` zet en `JWT_SECRET` staat nog op de dev default, stopt de app met een startup error.

## Snel starten

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Open daarna `http://127.0.0.1:8000/docs` voor Swagger UI.

## Screenshot runbook (heatmap)

Voor een reproduceerbare UI-screenshot van de capaciteit-heatmap: zie `docs/screenshots.md` en run:

```bash
bash scripts/capture_heatmap.sh
```

## Frontend (basic web UI)

Er is nu ook een eenvoudige frontend shell beschikbaar op `http://127.0.0.1:8000/` met de drie gevraagde schermen:

1. Login flow
2. Employees/Shifts beheer
3. Optimize-run + resultaatweergave (`score`, `score_breakdown`, assignments) + KPI/run history ophalen

De UI gebruikt dezelfde API endpoints en JWT-token als de Swagger flow.
Inclusief basis UX-polish: client-side validatie, loading states en delete-confirmaties in de forms.
Actieknoppen voor create/run starten disabled totdat je bent ingelogd; shift start/end krijgen default waarden.
List filters in de UI ondersteunen team/site/skill, sortering en limit/offset zodat je grotere datasets beter kunt beheren.
Na een optimize-run ververst de UI automatisch KPI en run history voor dezelfde scope-filters.
Run history ondersteunt ook nieuwste/ouder sortering in de UI en een offset-control voor paginatie.
Optimize-paneel layout is aangepast voor betere leesbaarheid met meerdere controls en bevat nu ook een `Reset View` actie.
Je kunt run/KPI/run-history JSON direct kopiëren via `Copy JSON` knoppen.
Er is ook een `Delete Latest Run` actie in de UI (planner) voor snelle cleanup van recente runs, inclusief bevestigingsprompt.


## Testen

```bash
PYTHONPATH=backend python -m unittest discover -s backend/tests -p 'test_*.py'
```

> Op omgevingen zonder FastAPI dependency worden API-contracttests automatisch als `skipped` gemarkeerd in plaats van hard te falen.

## Demo credentials (alleen development)

Tijdens startup worden dev users automatisch gecreëerd als `SEED_DEV_USERS=true`:

- planner / planner123
- viewer / viewer123

## Vervolgstappen (aanbevolen)

1. Dev user seeding standaard uit in staging/prod CI.
2. `POST /optimize` uitbreiden met geavanceerde route engine (basis route-weighting zit nu in planner v4).
3. Integratielaag toevoegen voor REEN/WasteVision/Qlik pipelines.
4. CI pipeline uitbreiden met linting/formatting gates naast tests.


## CI

Er is een GitHub Actions workflow toegevoegd op `.github/workflows/backend-ci.yml` die:

- draait op Python 3.10 en 3.11
- dependencies installeert
- `alembic upgrade head` uitvoert
- `ruff check backend` draait
- `black --check backend` draait
- daarna alle unit/API tests draait


## Code style

Lint/format configuratie staat in `pyproject.toml` (Ruff + Black).
