# ruff: noqa: E501
"""Structured, confirmable Fishbone causes without rewriting historical analysis."""

from alembic import op

revision = "0029_capa_fishbone_causes"
down_revision = "0028_capa_analysis_payload"
branch_labels = None
depends_on = None

VALIDATOR = r"""
CREATE OR REPLACE FUNCTION qms_capa_analysis_valid(method text, data jsonb) RETURNS boolean
LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE keys text[]; key text; value jsonb; nested_value jsonb; cause jsonb; statement text; evidence text; rationale text;
BEGIN
 IF method IS NULL OR data IS NULL OR jsonb_typeof(data)<>'object' OR octet_length(data::text)>100000 THEN RETURN false; END IF;
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
   FOR nested_value IN SELECT v FROM jsonb_each(value) AS x(k,v) LOOP
    IF jsonb_typeof(nested_value)<>'string' OR length(nested_value #>> '{}')>1000 THEN RETURN false; END IF;
   END LOOP;
  ELSIF method='fishbone' THEN
   -- Existing rows stored one string per category; they remain readable until edited.
   IF jsonb_typeof(value)='string' THEN
    IF length(value #>> '{}')>1000 THEN RETURN false; END IF;
   ELSIF jsonb_typeof(value)='array' THEN
    IF jsonb_array_length(value)>10 THEN RETURN false; END IF;
    FOR cause IN SELECT v FROM jsonb_array_elements(value) AS x(v) LOOP
     IF jsonb_typeof(cause)<>'object' THEN RETURN false; END IF;
     SELECT array_agg(k ORDER BY k) INTO keys FROM jsonb_object_keys(cause) AS x(k);
     IF keys IS DISTINCT FROM ARRAY['confirmed','evidence','rationale','statement']
      OR jsonb_typeof(cause->'statement')<>'string' OR jsonb_typeof(cause->'evidence')<>'string'
      OR jsonb_typeof(cause->'rationale')<>'string' OR jsonb_typeof(cause->'confirmed')<>'boolean' THEN RETURN false; END IF;
     statement:=cause->>'statement'; evidence:=cause->>'evidence'; rationale:=cause->>'rationale';
     IF length(btrim(statement))<1 OR length(statement)>1000 OR length(evidence)>2000 OR length(rationale)>2000 THEN RETURN false; END IF;
     IF cause->>'confirmed'='true' AND (length(btrim(evidence))<1 OR length(btrim(rationale))<1) THEN RETURN false; END IF;
    END LOOP;
   ELSE RETURN false;
   END IF;
  ELSIF jsonb_typeof(value)<>'string' OR length(value #>> '{}')>1000 THEN RETURN false;
  END IF;
 END LOOP;
 RETURN true;
END; $$;
"""

OLD_VALIDATOR = r"""
CREATE OR REPLACE FUNCTION qms_capa_analysis_valid(method text, data jsonb) RETURNS boolean
LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE keys text[]; key text; value jsonb; nested_key text; nested_value jsonb;
BEGIN
 IF method IS NULL OR data IS NULL OR jsonb_typeof(data)<>'object' OR octet_length(data::text)>100000 THEN RETURN false; END IF;
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
    op.execute(r"""
CREATE OR REPLACE FUNCTION qms_capa_analysis_scaffold(method text) RETURNS jsonb
LANGUAGE sql IMMUTABLE SECURITY INVOKER SET search_path=pg_catalog,public AS $$
 SELECT CASE method
  WHEN '5why' THEN '{"why1":"","why2":"","why3":"","why4":"","why5":""}'::jsonb
  WHEN 'fishbone' THEN '{"people":[],"process":[],"equipment":[],"materials":[],"measurement":[],"environment":[]}'::jsonb
  WHEN 'is_is_not' THEN '{"what":{"observed":"","not_observed":"","distinction":"","change":""},"where":{"observed":"","not_observed":"","distinction":"","change":""},"when":{"observed":"","not_observed":"","distinction":"","change":""},"extent":{"observed":"","not_observed":"","distinction":"","change":""}}'::jsonb
  WHEN 'other' THEN '{}'::jsonb
  ELSE NULL END;
$$;
""")
    op.execute(VALIDATOR)


def downgrade() -> None:
    op.execute(r"""
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM qms_capas c, jsonb_each(c.analysis_data) AS x(k,v)
  WHERE c.root_cause_method='fishbone' AND jsonb_typeof(x.v)='array') THEN
  RAISE EXCEPTION 'cannot discard structured Fishbone analysis';
 END IF;
END $$;
""")
    op.execute(r"""
CREATE OR REPLACE FUNCTION qms_capa_analysis_scaffold(method text) RETURNS jsonb
LANGUAGE sql IMMUTABLE SECURITY INVOKER SET search_path=pg_catalog,public AS $$
 SELECT CASE method
  WHEN '5why' THEN '{"why1":"","why2":"","why3":"","why4":"","why5":""}'::jsonb
  WHEN 'fishbone' THEN '{"people":"","process":"","equipment":"","materials":"","measurement":"","environment":""}'::jsonb
  WHEN 'is_is_not' THEN '{"what":{"observed":"","not_observed":"","distinction":"","change":""},"where":{"observed":"","not_observed":"","distinction":"","change":""},"when":{"observed":"","not_observed":"","distinction":"","change":""},"extent":{"observed":"","not_observed":"","distinction":"","change":""}}'::jsonb
  WHEN 'other' THEN '{}'::jsonb
  ELSE NULL END;
$$;
""")
    op.execute(OLD_VALIDATOR)
