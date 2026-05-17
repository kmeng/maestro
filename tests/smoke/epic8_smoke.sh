#!/usr/bin/env bash
# Epic 8 自动化烟测 (automated portion; manual portion in epic8.md)
#
# 覆盖：
# - librarian: file_paths multi-file XOR + soft cap on combined input
# - verifier: tool registration + schema shape + handler input_validation paths
# - spec_writer: tool registration + schema shape + handler input_validation paths
# - scribe: new schema required={diff, purpose}; old issue_* fields removed
# - SHIPPED_TOOL_IDS contains verifier + spec-writer; resolve bypass logic
# - DEFAULT_MODELS covers all 4 user roles + 2 shipped tools
# - render_savings _tool_breakdown_str includes 'v' and 'w' columns
#
# 真实 LLM 调用 / 外部 MCP client 验证留给 epic8.md + epic8_external.md。

set -euo pipefail
cd "$(dirname "$0")/../.."

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 1) Tool registry contains 6 roles + job_status
# ---------------------------------------------------------------------------

.venv/bin/python -c "
import importlib.util
spec = importlib.util.spec_from_file_location('m', 'maestro/mcp_server.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
expected = {'coder','librarian','reviewer','scribe','verifier','spec_writer','job_status'}
assert set(m.TOOLS_REGISTRY.keys()) == expected, f'got {set(m.TOOLS_REGISTRY.keys())}'
" || fail "TOOLS_REGISTRY missing one of: coder/librarian/reviewer/scribe/verifier/spec_writer/job_status"
pass "TOOLS_REGISTRY has six roles + job_status"

# ---------------------------------------------------------------------------
# 2) librarian schema has file_paths optional field
# ---------------------------------------------------------------------------

.venv/bin/python -c "
import importlib.util
spec = importlib.util.spec_from_file_location('m', 'maestro/mcp_server.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
props = m.LIBRARIAN_TOOL.inputSchema['properties']
assert 'file_paths' in props
assert props['file_paths']['type'] == 'array'
assert props['file_paths']['items'] == {'type': 'string'}
# file_paths is NOT required (XOR enforced at handler level)
assert 'file_paths' not in m.LIBRARIAN_TOOL.inputSchema['required']
" || fail "librarian file_paths schema malformed"
pass "librarian.inputSchema has file_paths array field (optional, XOR at handler)"

# ---------------------------------------------------------------------------
# 3) verifier schema shape
# ---------------------------------------------------------------------------

.venv/bin/python -c "
import importlib.util
spec = importlib.util.spec_from_file_location('m', 'maestro/mcp_server.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
schema = m.VERIFIER_TOOL.inputSchema
assert schema['required'] == ['claims']
props = schema['properties']
for k in ('claims', 'file_paths', 'document_text', 'task_id', 'issue_number'):
    assert k in props, f'missing {k}'
" || fail "verifier schema malformed"
pass "verifier.inputSchema required=[claims]; properties cover claims+file_paths+document_text+telemetry"

# ---------------------------------------------------------------------------
# 4) spec_writer schema shape
# ---------------------------------------------------------------------------

.venv/bin/python -c "
import importlib.util
spec = importlib.util.spec_from_file_location('m', 'maestro/mcp_server.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
schema = m.SPEC_WRITER_TOOL.inputSchema
required = set(schema['required'])
expected_required = {'task_description','acceptance_criteria','upstream_contracts','output_files','language'}
assert required == expected_required, f'got {required}'
props = schema['properties']
for k in ('shared_constraints', 'risk_markers', 'task_id', 'issue_number'):
    assert k in props, f'missing optional {k}'
assert m.SPEC_WRITER_TOOL.name == 'spec_writer'
" || fail "spec_writer schema malformed"
pass "spec_writer.inputSchema required = task_description/acceptance_criteria/upstream_contracts/output_files/language"

# ---------------------------------------------------------------------------
# 5) scribe new schema — required = {diff, purpose}; no GitHub-issue fields required
# ---------------------------------------------------------------------------

.venv/bin/python -c "
import importlib.util
spec = importlib.util.spec_from_file_location('m', 'maestro/mcp_server.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
required = set(m.SCRIBE_TOOL.inputSchema['required'])
assert required == {'diff', 'purpose'}, f'got {required}'
props = m.SCRIBE_TOOL.inputSchema['properties']
for old in ('issue_title', 'issue_body', 'convention'):
    assert old not in props, f'{old} should not be in scribe schema'
" || fail "scribe schema still leaks GitHub-issue concepts"
pass "scribe.inputSchema required={diff, purpose}; no issue_title/issue_body/convention"

# ---------------------------------------------------------------------------
# 6) SHIPPED_TOOL_IDS contains verifier + spec-writer
# ---------------------------------------------------------------------------

.venv/bin/python -c "
from maestro.team import SHIPPED_TOOL_IDS, ROLE_IDS, DEFAULT_MODELS
assert 'verifier' in SHIPPED_TOOL_IDS
assert 'spec-writer' in SHIPPED_TOOL_IDS
assert set(SHIPPED_TOOL_IDS).isdisjoint(set(ROLE_IDS))
assert DEFAULT_MODELS['verifier'] == 'deepseek-v4-flash'
assert DEFAULT_MODELS['spec-writer'] == 'deepseek-v4-flash'
assert set(DEFAULT_MODELS.keys()) == set(ROLE_IDS) | set(SHIPPED_TOOL_IDS)
" || fail "SHIPPED_TOOL_IDS / DEFAULT_MODELS not extended for Epic 8"
pass "SHIPPED_TOOL_IDS contains verifier + spec-writer; DEFAULT_MODELS covers them"

# ---------------------------------------------------------------------------
# 7) resolve_role_model bypasses team.yaml for shipped tools
# ---------------------------------------------------------------------------

.venv/bin/python -c "
from maestro.team import resolve_role_model, ResolveOk, DEFAULT_MODELS
from pathlib import Path
for tool in ('verifier', 'spec-writer'):
    result = resolve_role_model(tool, Path('/tmp'))
    assert isinstance(result, ResolveOk)
    assert result.model == DEFAULT_MODELS[tool]
    assert result.event is None
" || fail "resolve_role_model bypass broken for shipped tools"
pass "resolve_role_model: verifier + spec-writer bypass team.yaml correctly"

# ---------------------------------------------------------------------------
# 8) render_savings _tool_breakdown_str includes verifier and spec-writer columns
# ---------------------------------------------------------------------------

.venv/bin/python -c "
import importlib.util
spec = importlib.util.spec_from_file_location('rs', 'scripts/render_savings.py')
rs = importlib.util.module_from_spec(spec); spec.loader.exec_module(rs)
counts = {'coder': 1, 'librarian': 2, 'reviewer': 3, 'scribe': 4, 'verifier': 5, 'spec-writer': 6}
out = rs._tool_breakdown_str(counts)
assert 'v5' in out, f'verifier column missing: {out}'
assert 'w6' in out, f'spec-writer column missing: {out}'
assert out.startswith('21 ('), f'sum incorrect: {out}'
" || fail "render_savings _tool_breakdown_str does not include v/w columns"
pass "render_savings shows v + w columns for verifier + spec-writer"

# ---------------------------------------------------------------------------
# 9) librarian rejects oversize combined file_paths input (T8.1 cap)
# ---------------------------------------------------------------------------

.venv/bin/python -c "
import asyncio, json, importlib.util, tempfile, os
spec = importlib.util.spec_from_file_location('m', 'maestro/mcp_server.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
with tempfile.TemporaryDirectory() as d:
    a = os.path.join(d, 'a.md'); open(a,'w').write('x'*50000)
    b = os.path.join(d, 'b.md'); open(b,'w').write('y'*50000)
    r = asyncio.run(m._librarian_impl({'file_paths':[a,b], 'query':'x'}))
    err = json.loads(r[0].text)
    assert err.get('error') == 'document_too_large', f'got {err}'
" || fail "librarian did not reject oversize combined input"
pass "librarian rejects combined file_paths > MAX_DOCUMENT_CHARS"

# ---------------------------------------------------------------------------
# 10) verifier + spec_writer + scribe handlers run input_validation without LLM
# ---------------------------------------------------------------------------

.venv/bin/python -c "
import asyncio, json, importlib.util
spec = importlib.util.spec_from_file_location('m', 'maestro/mcp_server.py')
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
# verifier rejects no claims
r = asyncio.run(mod._verifier_impl({'document_text':'x'}))
assert json.loads(r[0].text)['error'] == 'input_validation'
# spec_writer rejects no task_description
r = asyncio.run(mod._spec_writer_impl({'acceptance_criteria':['x'],'upstream_contracts':'y','output_files':['a.py'],'language':'python'}))
assert json.loads(r[0].text)['error'] == 'input_validation'
# scribe rejects no purpose
r = asyncio.run(mod._scribe_impl({'diff':'x'}))
assert json.loads(r[0].text)['error'] == 'input_validation'
" || fail "handler input_validation paths broken"
pass "verifier / spec_writer / scribe all reject malformed input cleanly"

echo
echo "Epic 8 automated smoke: ALL PASS"
