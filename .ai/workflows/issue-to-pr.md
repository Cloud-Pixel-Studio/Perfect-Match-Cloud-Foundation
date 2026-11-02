# Controlled GitHub Issue → Pull Request workflow

The repository implements a planning-only intake gate in
`.github/workflows/agent-intake.yml`. It is manual (`workflow_dispatch`), verifies
the activation actor has `write`, `maintain` or `admin` permission, requires an
open issue carrying `ai:ready`, treats the issue body as untrusted data and emits
only a sanitized evidence manifest. It cannot edit source, push, open a pull
request, merge or deploy.

| Stage | Required state | Evidence | Human gate |
| --- | --- | --- | --- |
| Intake | `ai:ready` by authorized maintainer | scope, acceptance criteria, sensitive paths | Maintainer activation |
| Planning | `ai:planning` | architecture impact, threat notes, allowed files, test plan | Required for high-risk scope |
| Preservation | `ai:planning` | verified checkpoint manifest and restore status | Required before writes |
| Development | `ai:developing` | dedicated branch, bounded diff | No production access |
| Testing | `ai:testing` | unit/integration/regression and migration evidence | Fail closed |
| Security | `ai:security-review` | secrets, SAST, dependencies, tenant/RLS review | Security review for sensitive changes |
| Visual | `ai:visual-review` | masked screenshots, responsive matrix, axe/keyboard | Human baseline acceptance |
| Review | `ai:pr-ready` | independent review and rollback plan | Human PR approval |
| Merge/release | no autonomous label transition | successful protected CI | Human merge and deployment only |

The sequence is: issue form → maintainer applies `ai:ready` → maintainer manually
runs Controlled agent intake → checkpoint → architecture plan → bounded branch
work → tests/security/visual review → independent review → CP-06 → separately
authorized push and pull request. The issue body is evidence for planning only;
it is never evaluated as shell, code, tool arguments or agent policy.

Use `ai:blocked`, `ai:failed` and `ai:needs-human` when authority, evidence or a
material product decision is missing. Automated jobs must run with read-only
contents by default and receive the minimum additional permission per job. Fork PRs
and untrusted issue text never receive write tokens or secrets.
