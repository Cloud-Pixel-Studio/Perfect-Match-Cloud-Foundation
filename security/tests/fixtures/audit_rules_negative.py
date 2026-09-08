def safe_audit_service(record):
    return record


def audit_service_boundary():
    def _record():
        return AuditEvent(id="synthetic")

    return _record
