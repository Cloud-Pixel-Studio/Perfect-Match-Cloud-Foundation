# Development Governance

Changes follow: issue, feature branch, implementation, focused validation, full
checkpoint, pull request, review, Product Owner approval, and merge.

No contributor may force-push published history, delete `main`, merge their own
pull request, or close the primary mission issue without authorization. The one
empty-repository exception permits a governance-only base commit to `main`.

Branches use the `pmc/` namespace. Every checkpoint must be evidence-driven;
missing evidence is reported as PARTIAL, never inferred as PASS.

Scope is mission-bound. AWS provisioning, customer data, production credentials,
Odoo access, and unreviewed restrictive dependencies are prohibited during PMC-00.

## OWNER-ONLY GOVERNANCE RULE

Administrative, privileged, and irreversible repository actions are reserved
exclusively for the authorized GitHub Organization or Repository Owner account.
Automation agents, Codex, developers, reviewers, service accounts, and non-owner
accounts MUST NOT:

- merge pull requests into `main` or another protected or release branch;
- change repository visibility;
- change repository ownership;
- transfer or delete the repository;
- change repository-level permissions;
- add or remove collaborators or teams;
- modify branch protection or repository rulesets;
- create or change repository or environment secrets;
- change GitHub Actions administrative permissions;
- enable or modify auto-merge policy;
- force-push protected history;
- delete protected branches;
- approve their own privileged changes; or
- create official production releases unless specifically authorized by the Owner.

A PASS checkpoint and successful CI do not constitute merge authorization. The
required lifecycle is:

Issue -> branch -> implementation -> validation -> checkpoint -> PR -> review ->
OWNER APPROVAL -> OWNER-EXECUTED MERGE

The Owner may explicitly delegate non-administrative implementation work, but
administrative authority remains with the Owner unless the Owner formally
changes this governance policy. Codex may prepare changes, commits, issues, pull
requests, test results, and checkpoint evidence. Codex may not merge its own work.

## Public Repository and Proprietary Source

This repository is intentionally PUBLIC. Public visibility does not grant an
open-source license: Perfect Match Cloud remains proprietary and All Rights
Reserved. No secret, customer data, private key, production credential, or
confidential customer artifact may ever be committed.
