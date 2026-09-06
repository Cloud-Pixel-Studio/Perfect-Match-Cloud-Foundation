# Repository Protection Baseline

This document records the technical governance baseline for the `main` branch
of `Cloud-Pixel-Studio/Perfect-Match-Cloud-Foundation`. It complements
`DEVELOPMENT_GOVERNANCE.md`; it does not replace the Owner-only governance
policy in that document.

## Prior gap

Before PMC-00.4, the GitHub API reported `main` as unprotected, the branch
protection endpoint returned no configured protection, and the repository had
no rulesets. The repository therefore relied on governance policy and account
permissions without a technical pull-request or status-check gate on `main`.

## Active enforcement

Repository ruleset `22409098`, named `Protect main foundation gates`, is active
and targets only `refs/heads/main`. Its bypass actor list is empty.

| Control | Enforced baseline |
| --- | --- |
| Changes to `main` | Pull request required |
| Required checks | `backend`, `frontend`, `shell`, `security` |
| Check source | GitHub Actions integration ID `15368` |
| Branch freshness | Strict; the pull request head must be up to date |
| Review conversations | All conversations must be resolved |
| Approvals | No approval count is imposed by the technical rule |
| Force push | Blocked |
| Branch deletion | Blocked |
| Administrative CI bypass | None; the bypass actor list is empty |
| Linear history | Not required |
| Merge commit | Allowed |

The required checks were selected from successful checks observed on a current
pull request. The zero-approval technical setting is intentional: authorization
to merge is controlled by the Owner-only policy, while the ruleset independently
requires every actor, including the Owner and repository administrators, to
pass CI and use the pull-request path. A successful checkpoint or CI run does
not itself authorize a merge.

## Access snapshot

At establishment of this baseline, the authenticated Owner account
`BigPortilloUS` was the sole repository administrator and the only account with
merge-capable access. Account `raizo159` had read-only access. No team had
repository access, and the organization outside-collaborator listing did not
grant its listed account access to this repository.

Repository visibility remains intentionally public. Public visibility does not
grant an open-source license: Perfect Match Cloud remains proprietary and All
Rights Reserved. Secrets, customer data, private keys, production credentials,
and confidential customer artifacts must never be committed.

## Owner-only limitation

GitHub's pull-request rule does not independently restrict a compliant merge to
the organization Owner. A bypass entry could identify an Owner or administrator,
but that entry would also permit bypassing the required pull-request and CI
controls, which this baseline prohibits. The active ruleset therefore has no
bypass actors.

Owner-only merge execution is enforced by repository governance policy and is
effective under the access snapshot above. It is not independently encoded as
an actor-level merge restriction in the ruleset. Granting a non-owner `write`,
`maintain`, or `admin` role could make that actor technically able to merge a
compliant pull request. Repository permission changes remain Owner-only actions
and require a corresponding review of this baseline.

## Verification procedure

PMC-00.4 is verified through its dedicated issue, branch, and pull request. The
verification pull request must demonstrate that:

1. `main` cannot be updated outside the pull-request rule;
2. all four required checks succeed on the current, up-to-date head;
3. the pull request becomes mergeable only after the ruleset requirements pass;
4. the authenticated Owner executes a merge commit without administrative
   bypass; and
5. post-merge quality and security workflows succeed on the resulting `main`
   commit.

The feature branch is retained after verification as governance evidence.
