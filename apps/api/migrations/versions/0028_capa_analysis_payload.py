# ruff: noqa: E501
"""Allow bounded multibyte CAPA analysis text accepted by the API."""

from alembic import op

revision = "0028_capa_analysis_payload"
down_revision = "0027_qms_capa_analysis"
branch_labels = None
depends_on = None

VALIDATOR = r"""
CREATE OR REPLACE FUNCTION qms_capa_analysis_valid(method text, data jsonb) RETURNS boolean
LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE keys text[]; key text; value jsonb; nested_key text; nested_value jsonb;
BEGIN
 IF method IS NULL OR data IS NULL OR jsonb_typeof(data)<>'object' OR octet_length(data::text)>__BYTE_LIMIT__ THEN RETURN false; END IF;
 IF method='other' THEN RETURN data='{}'::jsonb; END IF;
 SELECT array_agg(k ORDER BY k) INTO keys FROM jsonb_object_keys(data) AS x(k);
 IF method='5why' AND keys IS DISTINCT FROM ARRAY['why1','why2','why3','why4','why5'] THEN RETURN false; END IF;
 IF method='fishbone' AND keys IS DISTINCT FROM ARRAY['environment','equipment','materials','measurement','people','process'] THEN RETURN false; END IF;
 IF method='is_is_not' AND keys IS DISTINCT FROM ARRAY['extent','what','when','where'] THEN RETURN false; END IF;
 IF method NOT IN ('5why','fishbone','is_is_not') THEN RETURN false; END IF;
 FOR key,value IN SELECT k,v FROM jsonb_each(data) AS x(k,v) LOOP
  IF method='is_is_not' THEN
   IF jsonb_typeof(value)<>'object' THEN RETURN false; END IF;
   SELECT array_agg(k ORDER BY k) INTO keys FROM jsonb_object_keys(value) AS x(k);
   IF keys IS DISTINCT FROM ARRAY['change','distinction','not_observed','observed'] THEN RETURN false; END IF;
   FOR nested_key,nested_value IN SELECT k,v FROM jsonb_each(value) AS x(k,v) LOOP
    IF jsonb_typeof(nested_value)<>'string' OR length(nested_value #>> '{}')>1000 THEN RETURN false; END IF;
   END LOOP;
  ELSIF jsonb_typeof(value)<>'string' OR length(value #>> '{}')>1000 THEN RETURN false;
  END IF;
 END LOOP;
 RETURN true;
END; $$;
"""


def upgrade() -> None:
    op.execute(VALIDATOR.replace("__BYTE_LIMIT__", "100000"))


def downgrade() -> None:
    op.execute(r"""
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM qms_capas WHERE octet_length(analysis_data::text)>24000) THEN
  RAISE EXCEPTION 'cannot restore previous CAPA analysis limit with existing content';
 END IF;
END $$;
""")
    op.execute(VALIDATOR.replace("__BYTE_LIMIT__", "24000"))
