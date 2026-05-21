# Modernization audit (Frappe app)

This audit follows `docs/frappe-app-standards-modernization-playbook.md` and is intended to create a prioritized backlog before any modernization edits.

## App / version assumptions

- **Bench path**: `/home/beeta/prakash-bench`
- **App under audit**: `prakash_steel` (reported by `bench version` as `0.0.1`)
- **Frappe / ERPNext** (from `bench version`):
  - `frappe 15.76.0`
  - `erpnext 15.73.0`
  - `hrms 15.48.0`
  - `india_compliance 15.22.0`
  - `crm 2.0.0-dev`
  - plus other installed apps (see command output section)
- **Site**: `praksh.com`
- **Python**: 3.10 (inferred from stacktrace paths: `/usr/lib/python3.10/...`)

## Commands attempted and results

### `bench version`

- **Command**:

```bash
cd /home/beeta/prakash-bench && bench version
```

- **Result**: success

```text
clapgrow_app 1.0.0
clapgrow_workflow 0.0.1
commit 1.0.0
crm 2.0.0-dev
erpnext 15.73.0
frappe 15.76.0
hrms 15.48.0
india_compliance 15.22.0
lms 2.33.0
prakash_steel 0.0.1
wiki 2.0.0
```

### `bench --site praksh.com migrate`

- **Command**:

```bash
cd /home/beeta/prakash-bench && bench --site "praksh.com" migrate
```

- **Result**: success (`exit_code: 0`)
- **Observed output** (excerpt): DocTypes updated for multiple apps; `after_migrate` hooks executed; search index rebuild queued.

### `bench --site praksh.com run-tests --app prakash_steel`

- **Command**:

```bash
cd /home/beeta/prakash-bench && bench --site "praksh.com" run-tests --app "prakash_steel"
```

- **Result**: failed before tests ran, during test record setup.
- **Failure**:
  - Exception: `frappe.exceptions.ValidationError`
  - Message: `GST Rate cannot be zero for Taxable GST Treatment`
  - Origin: `india_compliance/gst_india/overrides/item_tax_template.py` (validate hook)

### `bench --site praksh.com run-tests --app prakash_steel --skip-test-records`

- **Command**:

```bash
cd /home/beeta/prakash-bench && bench --site "praksh.com" run-tests --app "prakash_steel" --skip-test-records
```

- **Result**: success

```text
Ran 67 tests in 0.195s
OK
```

## Findings (P0 / P1 / P2 / P3)

### P0 (release blockers)

#### P0-001: Test baseline cannot run (`bench run-tests --app prakash_steel` fails)

- **Why it matters**: The playbook requires freezing a baseline and improving safety with targeted tests. Right now the baseline is not executable due to an upstream validation error triggered while creating test records.
- **Evidence**:
  - Command: `bench --site "praksh.com" run-tests --app "prakash_steel"`
  - Error: `GST Rate cannot be zero for Taxable GST Treatment` from `india_compliance` validate hook.
- **Likely remediation path** (smallest-first):
  - **Short-term baseline**: run tests with `--skip-test-records` (currently passes) to get signal while triaging higher-risk findings.
  - **Proper fix**: make test-record creation pass on a disposable test site (or adjust the failing test-record setup to satisfy `india_compliance` constraints), so tests also run without `--skip-test-records`.
  - Document the exact minimal steps needed so CI can reproduce.

### P1 (unsafe maintainability debt / permission and data-risk hotspots)

#### P1-001: Many whitelisted methods (API surface needs permission + input validation review)

- **Why it matters**: Whitelisted methods are the most common permission-bypass and input-validation risk in Frappe apps; they also become external contracts quickly.
- **Evidence**: `@frappe.whitelist()` appears across many modules, including:
  - `prakash_steel/prakash_steel/doctype/mrp_genaration/mrp_genaration.py` (multiple)
  - `prakash_steel/prakash_steel/report/*/*.py` (multiple reports expose whitelisted helpers)
  - `prakash_steel/api/*.py` (dashboards + “get last rate/qty” style endpoints)
  - `prakash_steel/utils/*` (cancel flows, lead_time, etc.)
- **Risk to prioritize within this**:
  - Any `allow_guest=True` (none found in this scan) would be an immediate escalator.
  - Any whitelist that accepts arbitrary `doctype/name/filters` without allowlists.
  - Any whitelist that calls `frappe.get_doc` and returns doc data without permission checks.

#### P1-002: `ignore_permissions=True` used in inserts/saves (requires explicit permission decision + tests)

- **Why it matters**: The playbook treats `ignore_permissions=True` as a red flag unless the permission decision is documented and tested; it can create bypasses and audit gaps.
- **Evidence (examples)**:
  - `prakash_steel/prakash_steel/report/po_recomendation_for_psp/po_recomendation_for_psp.py`: `doc.insert(ignore_permissions=True)`
  - `prakash_steel/overrides/sales_invoice.py`: `stock_entry.insert(ignore_permissions=True)`
  - Multiple snapshot doctypes/pages insert snapshot docs with `ignore_permissions=True`
  - Patches inserting docs with `ignore_permissions=True`:
    - `prakash_steel/patches/v1_2_so_snapshot_client_script.py`
    - `prakash_steel/patches/v1_3_po_rec_snapshot_client_script.py`

#### P1-003: Heavy use of raw SQL via `frappe.db.sql(...)` (needs parameterization + semantics tests)

- **Why it matters**: The playbook requires parameter binding (no interpolation of request-controlled values) and cautions against mechanical rewrites where accounting/stock semantics exist.
- **Evidence**: `frappe.db.sql(` appears throughout:
  - Reports (e.g. `open_mr_for_*`, `po_recomendation_for_psp`, multiple trackers)
  - Dashboards and APIs
  - DocType controllers
  - Patches
- **Immediate triage questions**:
  - Are queries fully parameterized (`values=...` / `%s`)?
  - Do any queries build SQL strings from user inputs (filters, item codes, dates, warehouses)?
  - Do any queries touch ledger/stock tables where semantics require regression tests?

### P2 (standards drift / future risk)

#### P2-001: Permission checks are not consistently visible near data access

- **Evidence**: Limited direct matches for `frappe.has_permission` / `check_permission` in the scan results; at least two checks exist in `tog_calculation_report.py`.
- **Why it matters**: With many whitelisted methods + `frappe.get_doc` usage, permission enforcement should be explicit at the API boundary.

### P3 (cosmetic / consistency)

- Deferred per playbook. No repo-wide formatting work should start until P0/P1 are triaged.

## Tests that currently exist

`test_*.py` files were found under the app, primarily DocType-scoped tests. Examples include:

- `prakash_steel/doctype/*/test_*.py` (e.g. `billet_cutting`, `bright_bar_production`, `finish_weight`, `mrp_genaration`, etc.)
- `po_recommendation_history/doctype/*/test_*.py` (snapshot doctypes)

## Tests missing for risky behavior (recommended)

Given the findings above, high-value missing tests likely include:

- **Whitelisted API tests**:
  - Permission-denied cases (guest / non-privileged user) for each whitelisted endpoint
  - Input validation for types/ranges (dates, item codes, warehouse, company, fiscal year)
- **Raw SQL regression tests**:
  - For the most business-critical queries (procurement/planning/recommendation logic), assert outputs on seeded records.
- **Permission-bypass decisions**:
  - Any path that uses `ignore_permissions=True` should have tests proving it is only reachable/usable under intended roles or controlled server-side conditions.
- **Patch tests / migration safety checks** (at least smoke-level):
  - Patches should be idempotent and safe on partially migrated sites.

## Migration surface area (patches)

`prakash_steel/patches.txt` contains:

- `prakash_steel.patches.post_2026_04_add_gross_amount_and_backfill`
- `prakash_steel.patches.post_2026_04_purchase_invoice_gross_amount_and_backfill`
- `prakash_steel.patches.v1_2_so_snapshot_client_script`
- `prakash_steel.patches.v1_3_po_rec_snapshot_client_script`

## Recommended fix order

1. **P0-001**: Keep baseline green with `--skip-test-records`, then fix the test-record creation failure so tests also pass without this flag.
2. **P1-001**: Triage whitelisted methods (catalog endpoints, identify those that accept user inputs, and ensure explicit permission + input validation).
3. **P1-002**: Audit and document all `ignore_permissions=True` usage; add regression tests for the intended permission decisions.
4. **P1-003**: Audit raw SQL for injection risk and correctness; add tests before any refactor; then parameterize/replace selectively (prefer `frappe.qb` where feasible).
5. **Patches**: Verify patch idempotency and safety; add operator notes if any patch is destructive or has assumptions.
6. Only after the above stabilizes: tooling/formatting adoption in small reviewed batches (P3).
