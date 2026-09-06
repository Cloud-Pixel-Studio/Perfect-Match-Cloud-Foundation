# Architecture Baseline

Perfect Match Cloud is architected as SaaS from day one, including multiple
customers and organizations, tenant isolation, subscription-aware behavior,
horizontal deployment, cloud object storage, managed database, and enterprise
identity boundaries.

Initial domain language anticipates Tenant, Organization, Site, Department,
User, Membership, Role, Permission, and AuditEvent. Business resources will be
tenant-scoped. Full domain implementation is deferred.

Future audit records must support tenant, actor, action, resource type and ID,
old and new values, timestamp, and request ID, with optional network and
correlation context.

## Foundation topology

- Next.js web application calls the FastAPI service.
- FastAPI uses PostgreSQL through SQLAlchemy and Alembic.
- A Perfect Match storage interface owns standard S3 operations.
- Local storage uses the SeaweedFS S3-compatible gateway.
- Future production storage maps to Amazon S3 through configuration, without
  changing business logic.

Local PostgreSQL maps conceptually to Amazon RDS PostgreSQL; containers map to a
future ECS/Fargate deployment; secrets map to Secrets Manager or Parameter Store;
email maps to SES; and future AI may map to Bedrock. PMC-00 provisions no AWS
resources and leaves `infrastructure/aws/` documentation-only.
