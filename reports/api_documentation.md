# API documentation

Start the service from the repository root after the artifacts exist:

```bash
uvicorn api.main:app --reload
```

Interactive schema: `/docs`.

| Method | Path | Role |
| --- | --- | --- |
| POST | `/api/valuation/predict` | Estimate, interval, classification, comparables, trend, reliability, model version |
| POST | `/api/valuation/comparables` | Similar earlier sales and similarity scores |
| GET | `/api/market/overview` | Primary-sale market totals and monthly/quarterly series |
| GET | `/api/communities` | Community index |
| GET | `/api/communities/{community_id}` | One community |
| GET | `/api/communities/{community_id}/trends` | Monthly and quarterly series |
| POST | `/api/communities/compare` | Two to five communities on the same filters |
| GET | `/api/map/communities` | Metrics with null geometry unless an external GeoJSON is joined |
| GET | `/api/model/methodology` | Coverage, features, split, test metrics, limitations |

Community ids look like `master__dubai-marina` and `area__marsa-dubai`. `DownTown Dubai` is the spelling in the file. `Downtown Dubai` is accepted as an alias.

Errors use `{"error": {"code", "message", "details"}}`. Unknown or thin communities return 422 rather than a number. Invalid JSON fields return 422. More than 60 requests per minute from one IP return 429.

Asking price is required for `/predict` and is not passed into the model.
