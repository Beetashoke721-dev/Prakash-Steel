# Agent operating brief (Frappe modernization)

When modernizing this Frappe app:

- Read `docs/frappe-app-standards-modernization-playbook.md` first and treat it as the operating brief (not a summary).
- Follow its P0/P1/P2/P3 severity model.
- Start with an audit prompt and produce `docs/modernization-audit.md` before making fixes.
- Do not do repo-wide formatting before security, migration, permission, and test-baseline issues are triaged.
- Keep each change scoped to one issue or one audit finding.

Guardrails:

- Do not run automatic repo-wide formatting.
- Do not change generated DocType JSON unless required.
- Do not modify patches without explaining migration safety.
- Do not use `ignore_permissions=True` unless the permission decision is documented and tested.
- Do not replace raw SQL mechanically if the query has business/accounting semantics; first add tests.
