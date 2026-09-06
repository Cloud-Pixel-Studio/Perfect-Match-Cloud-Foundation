# ADR 0001: Local S3-Compatible Object Storage

Status: Accepted for PMC-00

## Decision

Use Apache-2.0 SeaweedFS Community Edition 4.45 through its S3-compatible API
for local development only. Application code depends on the Perfect Match
`ObjectStorage` protocol and standard S3 operations, not SeaweedFS APIs.

## Context

The original MinIO requirement conflicted with the product's AGPL prohibition.
The Product Owner removed MinIO and approved canonical SeaweedFS Community
Edition after license review.

## Consequences

Local data is disposable and held in a named Docker volume. S3 is exposed only
on host loopback, credentials live outside the repository, and anonymous access
is denied. Future production uses Amazon S3 through configuration without
business-logic changes. No AWS resources are created by this decision.
