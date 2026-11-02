# Perfect Match QMS agent control plane

This directory defines roles and controls for assisted engineering. It does not
install an agent runtime or grant access by itself.

- `agents/team.yaml` is the role and permission matrix.
- `policies/operating-policy.md` defines non-negotiable safety boundaries.
- `workflows/issue-to-pr.md` defines the controlled Issue-to-PR lifecycle.
- `checkpoints/README.md` defines checkpoint evidence and recovery requirements.

Only maintainers may activate work by applying `ai:ready`. Issue text, comments,
attachments and external content are untrusted data. Humans retain approval of
migrations, security policies, dependencies, visual baselines, billing/licensing,
pull-request merge and every deployment.
