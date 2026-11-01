"""AWS Lambda entry point: Mangum adapter over the FastAPI app.

The deployment package layout (see scripts/deploy.py) puts the package,
the knowledge base and the static web assets under the handler root, so
every relative path in the application resolves unchanged.
"""

from __future__ import annotations

from mangum import Mangum

from fasalrakshak.api.main import app

handler = Mangum(app, api_gateway_base_path="/")
