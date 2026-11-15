#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
artifact="$PWD/infra/.build/lambda"
# Never ship a placeholder worker or claim a valid native artifact prematurely.
for handler in backend/aplomb/api/lambda_handler.py backend/aplomb/agents/worker.py; do
  if [[ ! -f "$handler" ]]; then printf 'Cannot package: required real handler missing: %s\n' "$handler" >&2; exit 1; fi
done
mkdir -p infra/.build
uv export --frozen --no-dev --no-emit-project --format requirements-txt > infra/.build/requirements.txt
rm -rf "$artifact"
mkdir -p "$artifact"
uv pip install --python-version 3.12 --python-platform x86_64-manylinux_2_28 \
  --only-binary :all: --target "$artifact" -r infra/.build/requirements.txt
cp -R backend/aplomb "$artifact/aplomb"
find "$artifact" -type d -name __pycache__ -prune -exec rm -rf {} +
# Native extension imports must be checked in the actual Lambda Python/architecture.
# Pin the runtime image used for the import check.
docker run --rm --platform linux/amd64 --entrypoint python \
  -v "$artifact:/var/task:ro" public.ecr.aws/lambda/python:3.12@sha256:696fcc2a052fc8f335f9b34c6ec4e50ad54dbe5dd35134ec997c4f97bd150b22 \
  -c 'import pydantic_core, mangum, boto3; from aplomb.optimizer.services import build_domain_services; from aplomb.api.lambda_handler import handler; from aplomb.agents.worker import handler as worker; assert callable(handler) and callable(worker) and callable(build_domain_services)'
python3 - "$artifact" <<'PY'
import hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1])
files = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in sorted(root.rglob('*')) if p.is_file()}
(root / 'aplomb-artifact.json').write_text(json.dumps({
    'runtime': 'python3.12', 'architecture': 'x86_64',
    'lambdaRuntimeImportCheck': True, 'files': files}, indent=2) + '\n')
PY
printf 'Lambda-compatible artifact: %s\n' "$artifact"
