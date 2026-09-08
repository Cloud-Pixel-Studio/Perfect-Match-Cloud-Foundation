from fastapi import APIRouter

router = APIRouter()


@router.post("/audit/events")
def write_audit_event():
    return {"ok": True}


def direct_audit_construction():
    return AuditEvent(id="synthetic")
