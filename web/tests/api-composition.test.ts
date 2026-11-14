import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { validateContract } from '../src/contracts/validate.js';

const root = fileURLToPath(new URL('../../', import.meta.url));

test('actual FastAPI responses satisfy the web contracts', () => {
  const python = path.join(root,
    process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');
  const serialized = execFileSync(python, ['-c', `
import json
from fastapi.testclient import TestClient
from aplomb.api.app import create_app
from aplomb.api.settings import Settings

session = {"X-Aplomb-Session": "s_00000000-0000-4000-8000-000000000001"}
rows = []
with TestClient(create_app(Settings(data_version="snap-20261113-starter")),
                raise_server_exceptions=False) as client:
    for contract, method, url, kwargs, expected in [
        ("HealthResponse", "GET", "/v1/health", {}, 200),
        ("Meta", "GET", "/v1/meta", {}, 200),
        ("ApiError", "GET", "/v1/profiles", {}, 422),
        ("ApiError", "GET", "/v1/profiles", {"headers": session}, 503),
        ("ApiError", "POST", "/v1/check", {"headers": session,
            "json": {"profileId": "robert", "move": None}}, 503),
        ("ApiError", "GET", "/v1/world/events", {"headers": session}, 501),
    ]:
        response = client.request(method, url, **kwargs)
        assert response.status_code == expected, (url, response.status_code, response.text)
        assert response.headers.get("x-request-id"), url
        assert response.headers.get("x-aplomb-data-version") == "snap-20261113-starter", url
        body = response.json()
        if contract == "ApiError":
            assert body["error"]["requestId"] == response.headers["x-request-id"]
        rows.append({"contract": contract, "body": body})
print(json.dumps(rows))
`], { cwd: root, encoding: 'utf8' });
  const responses = JSON.parse(serialized) as {
    contract: 'HealthResponse' | 'Meta' | 'ApiError'; body: unknown;
  }[];
  assert.equal(responses.length, 6);
  for (const row of responses) validateContract(row.contract, row.body);
  const meta = validateContract('Meta', responses[1]?.body);
  assert.equal(meta.universe.total, 0);
  assert.ok(Object.values(meta.features).every(value => value === false));
});
