# Inventario de operaciones API — 14 noviembre 2026

180 operaciones de producto/131paths:176decoradas+4comandos documentales de fábrica. No incluye /openapi.json del framework.

Entrada observada puede ser denegación/error/llamada Python directa: no acredita éxito HTTP ni todos los estados. La columna HTTP cuenta únicamente respuestas2xx de los tres casos dedicados PASS, con SQL aislado y AV/S3 en memoria. M01 conserva dos XFAILstrict, nunca PASS.

| Módulo | Operación | Función | Entrada observada | Casos PASS con HTTP2xx acotado |
| --- | --- | --- | --- | ---: |
| action_center | `GET /action-center` | `action_center.py:action_center` | Sí, acotada | 1 |
| audit | `GET /audit/events` | `audit.py:events` | Sí, acotada | 0 |
| auth | `GET /auth/callback` | `auth.py:callback` | Sí, acotada | 0 |
| auth | `GET /auth/login` | `auth.py:login` | Sí, acotada | 0 |
| auth | `POST /auth/logout` | `auth.py:logout` | Sí, acotada | 0 |
| auth | `GET /auth/me` | `auth.py:me` | Sí, acotada | 0 |
| auth | `POST /auth/tenant` | `auth.py:select_tenant` | Sí, acotada | 1 |
| auth | `GET /auth/tenants` | `auth.py:tenants` | Sí, acotada | 0 |
| capa | `GET /capas` | `capa.py:list_capas` | Sí, acotada | 0 |
| capa | `POST /capas` | `capa.py:create_capa` | Sí, acotada | 1 |
| capa | `GET /capas/{capa_id}` | `capa.py:get_capa` | Sí, acotada | 0 |
| capa | `PATCH /capas/{capa_id}` | `capa.py:update_capa` | Sí, acotada | 0 |
| capa | `GET /capas/{capa_id}/actions` | `capa.py:list_capa_actions` | Sí, acotada | 0 |
| capa | `POST /capas/{capa_id}/actions` | `capa.py:create_capa_action` | Sí, acotada | 1 |
| capa | `GET /capas/{capa_id}/actions/{action_id}` | `capa.py:get_capa_action` | Sí, acotada | 0 |
| capa | `PATCH /capas/{capa_id}/actions/{action_id}` | `capa.py:update_capa_action` | Sí, acotada | 0 |
| capa | `POST /capas/{capa_id}/actions/{action_id}/transition` | `capa.py:transition_capa_action` | Sí, acotada | 0 |
| capa | `PATCH /capas/{capa_id}/analysis` | `capa.py:update_analysis` | Sí, acotada | 1 |
| capa | `POST /capas/{capa_id}/analysis/start` | `capa.py:start_analysis` | Sí, acotada | 1 |
| capa | `POST /capas/{capa_id}/cancel` | `capa.py:cancel_capa` | Sí, acotada | 0 |
| capa | `POST /capas/{capa_id}/close` | `capa.py:close_capa` | Sí, acotada | 0 |
| capa_trace_links | `GET /capas/{capa_id}/control-links` | `capa_trace_links.py:list_control_links` | Sí, acotada | 0 |
| capa_trace_links | `POST /capas/{capa_id}/control-links` | `capa_trace_links.py:add_control_link` | Sí, acotada | 0 |
| capa_trace_links | `POST /capas/{capa_id}/control-links/{link_id}/remove` | `capa_trace_links.py:remove_control_link` | Sí, acotada | 0 |
| capa_links | `GET /capas/{capa_id}/document-links` | `capa_links.py:list_document_links` | Sí, acotada | 0 |
| capa_links | `POST /capas/{capa_id}/document-links` | `capa_links.py:add_document_link` | Sí, acotada | 0 |
| capa_links | `POST /capas/{capa_id}/document-links/{link_id}/remove` | `capa_links.py:remove_document_link` | Sí, acotada | 0 |
| capa | `POST /capas/{capa_id}/effectiveness-review/start` | `capa.py:start_effectiveness_review` | Sí, acotada | 0 |
| capa | `GET /capas/{capa_id}/effectiveness-reviews` | `capa.py:list_effectiveness_reviews` | Sí, acotada | 0 |
| capa | `POST /capas/{capa_id}/effectiveness-reviews` | `capa.py:record_effectiveness_review` | Sí, acotada | 0 |
| capa_trace_links | `GET /capas/{capa_id}/evidence-links` | `capa_trace_links.py:list_evidence_links` | No; implementada sin esta observación | 0 |
| capa_trace_links | `POST /capas/{capa_id}/evidence-links` | `capa_trace_links.py:add_evidence_link` | Sí, acotada | 0 |
| capa_trace_links | `POST /capas/{capa_id}/evidence-links/{link_id}/remove` | `capa_trace_links.py:remove_evidence_link` | No; implementada sin esta observación | 0 |
| capa | `POST /capas/{capa_id}/implementation/start` | `capa.py:start_implementation` | Sí, acotada | 0 |
| capa | `POST /capas/{capa_id}/plan/start` | `capa.py:start_plan` | Sí, acotada | 1 |
| control_definitions | `PATCH /control-activities/{activity_id}` | `control_definitions.py:update_activity` | Sí, acotada | 0 |
| control_definitions | `PATCH /control-evidence-requirements/{requirement_id}` | `control_definitions.py:update_evidence_requirement` | Sí, acotada | 0 |
| control_instance_activities | `GET /control-instance-activities` | `control_instance_activities.py:list_activities` | Sí, acotada | 1 |
| control_instance_activities | `PATCH /control-instance-activities/{activity_id}` | `control_instance_activities.py:update_activity` | Sí, acotada | 1 |
| control_instance_activities | `POST /control-instance-activities/{activity_id}/transition` | `control_instance_activities.py:transition_activity` | Sí, acotada | 0 |
| control_instance_evidence | `GET /control-instance-evidence` | `control_instance_evidence.py:list_evidence` | Sí, acotada | 1 |
| control_instance_evidence | `PATCH /control-instance-evidence/{evidence_id}` | `control_instance_evidence.py:update_evidence` | Sí, acotada | 1 |
| control_instance_evidence | `POST /control-instance-evidence/{evidence_id}/review` | `control_instance_evidence.py:review_evidence` | Sí, acotada | 0 |
| control_instance_evidence | `POST /control-instance-evidence/{evidence_id}/submit` | `control_instance_evidence.py:submit_evidence` | Sí, acotada | 1 |
| controls | `GET /control-instances` | `controls.py:list_instances` | Sí, acotada | 0 |
| controls | `POST /control-instances` | `controls.py:create_instance_route` | Sí, acotada | 1 |
| controls | `GET /control-instances/{instance_id}` | `controls.py:get_instance` | Sí, acotada | 0 |
| controls | `PATCH /control-instances/{instance_id}` | `controls.py:update_instance_route` | No; implementada sin esta observación | 0 |
| controls | `POST /control-instances/{instance_id}/transition` | `controls.py:transition_instance_route` | No; implementada sin esta observación | 0 |
| controls | `GET /controls` | `controls.py:list_controls` | No; implementada sin esta observación | 0 |
| controls | `POST /controls` | `controls.py:create_control_route` | Sí, acotada | 1 |
| controls | `GET /controls/{control_id}` | `controls.py:get_control` | Sí, acotada | 1 |
| controls | `PATCH /controls/{control_id}` | `controls.py:update_control_route` | No; implementada sin esta observación | 0 |
| controls | `POST /controls/{control_id}/activate` | `controls.py:activate_control_route` | Sí, acotada | 1 |
| control_definitions | `GET /controls/{control_id}/activities` | `control_definitions.py:list_activities` | No; implementada sin esta observación | 0 |
| control_definitions | `POST /controls/{control_id}/activities` | `control_definitions.py:create_activity` | Sí, acotada | 1 |
| control_definitions | `GET /controls/{control_id}/evidence-requirements` | `control_definitions.py:list_evidence_requirements` | No; implementada sin esta observación | 0 |
| control_definitions | `POST /controls/{control_id}/evidence-requirements` | `control_definitions.py:create_evidence_requirement` | Sí, acotada | 1 |
| controls | `POST /controls/{control_id}/retire` | `controls.py:retire_control_route` | No; implementada sin esta observación | 0 |
| documents | `GET /documents` | `documents.py:list_documents` | Sí, acotada | 0 |
| documents | `POST /documents` | `documents.py:create_document` | Sí, acotada | 3 |
| documents | `GET /documents/processes` | `documents.py:document_processes` | No; implementada sin esta observación | 0 |
| documents | `POST /documents/{document_id}/obsolete` | `documents.py:obsolete_document` | Sí, acotada | 0 |
| documents | `GET /documents/{document_id}/revisions` | `documents.py:revisions` | Sí, acotada | 3 |
| documents | `POST /documents/{document_id}/revisions` | `documents.py:create_revision` | Sí, acotada | 3 |
| documents | `POST /documents/{document_id}/revisions/{revision_id}/approve` | `documents.py:_endpoint_factory.<locals>.endpoint` | Sí, acotada | 2 |
| documents | `GET /documents/{document_id}/revisions/{revision_id}/file` | `documents.py:download_revision_file` | Sí, acotada | 1 |
| documents | `PUT /documents/{document_id}/revisions/{revision_id}/file` | `documents.py:quarantine_revision_file` | Sí, acotada | 3 |
| documents | `POST /documents/{document_id}/revisions/{revision_id}/reject` | `documents.py:_endpoint_factory.<locals>.endpoint` | Sí, acotada | 1 |
| documents | `POST /documents/{document_id}/revisions/{revision_id}/release` | `documents.py:_endpoint_factory.<locals>.endpoint` | Sí, acotada | 2 |
| documents | `POST /documents/{document_id}/revisions/{revision_id}/submit` | `documents.py:_endpoint_factory.<locals>.endpoint` | Sí, acotada | 2 |
| main | `GET /health` | `main.py:health` | Sí, acotada | 0 |
| internal_audits | `GET /internal-audits/audits` | `internal_audits.py:list_audits` | Sí, acotada | 0 |
| internal_audits | `POST /internal-audits/audits` | `internal_audits.py:create_audit` | Sí, acotada | 0 |
| internal_audits | `GET /internal-audits/audits/{audit_id}` | `internal_audits.py:get_audit` | Sí, acotada | 0 |
| internal_audits | `PATCH /internal-audits/audits/{audit_id}` | `internal_audits.py:update_audit` | Sí, acotada | 0 |
| internal_audit_agenda | `GET /internal-audits/audits/{audit_id}/agenda` | `internal_audit_agenda.py:list_agenda` | Sí, acotada | 0 |
| internal_audit_agenda | `POST /internal-audits/audits/{audit_id}/agenda` | `internal_audit_agenda.py:create_agenda_item` | Sí, acotada | 0 |
| internal_audit_agenda | `PATCH /internal-audits/audits/{audit_id}/agenda/{agenda_id}` | `internal_audit_agenda.py:update_agenda_item` | Sí, acotada | 0 |
| internal_audit_agenda | `POST /internal-audits/audits/{audit_id}/agenda/{agenda_id}/withdraw` | `internal_audit_agenda.py:withdraw_agenda_item` | Sí, acotada | 0 |
| internal_audit_competence | `GET /internal-audits/audits/{audit_id}/competence` | `internal_audit_competence.py:get_competence` | Sí, acotada | 0 |
| internal_audit_competence | `GET /internal-audits/audits/{audit_id}/competence/documents` | `internal_audit_competence.py:list_documents` | Sí, acotada | 0 |
| internal_audit_competence | `GET /internal-audits/audits/{audit_id}/competence/reviews` | `internal_audit_competence.py:list_reviews` | Sí, acotada | 0 |
| internal_audit_competence | `POST /internal-audits/audits/{audit_id}/competence/reviews` | `internal_audit_competence.py:create_review` | Sí, acotada | 0 |
| internal_audit_criteria | `GET /internal-audits/audits/{audit_id}/criteria` | `internal_audit_criteria.py:list_criteria` | Sí, acotada | 0 |
| internal_audit_criteria | `POST /internal-audits/audits/{audit_id}/criteria` | `internal_audit_criteria.py:create_criterion` | Sí, acotada | 0 |
| internal_audit_criteria | `PATCH /internal-audits/audits/{audit_id}/criteria/{criterion_id}` | `internal_audit_criteria.py:update_criterion` | Sí, acotada | 0 |
| internal_audit_criteria | `POST /internal-audits/audits/{audit_id}/criteria/{criterion_id}/withdraw` | `internal_audit_criteria.py:withdraw_criterion` | Sí, acotada | 0 |
| internal_audit_independence | `GET /internal-audits/audits/{audit_id}/independence` | `internal_audit_independence.py:get_independence` | Sí, acotada | 0 |
| internal_audit_independence | `GET /internal-audits/audits/{audit_id}/independence/reviews` | `internal_audit_independence.py:list_reviews` | Sí, acotada | 0 |
| internal_audit_independence | `POST /internal-audits/audits/{audit_id}/independence/reviews` | `internal_audit_independence.py:create_review` | Sí, acotada | 0 |
| internal_audit_scope | `GET /internal-audits/audits/{audit_id}/scopes` | `internal_audit_scope.py:list_scopes` | Sí, acotada | 0 |
| internal_audit_scope | `POST /internal-audits/audits/{audit_id}/scopes` | `internal_audit_scope.py:create_scope` | Sí, acotada | 0 |
| internal_audit_scope | `PATCH /internal-audits/audits/{audit_id}/scopes/{scope_id}` | `internal_audit_scope.py:update_scope` | Sí, acotada | 0 |
| internal_audit_scope | `POST /internal-audits/audits/{audit_id}/scopes/{scope_id}/withdraw` | `internal_audit_scope.py:withdraw_scope` | Sí, acotada | 0 |
| internal_audit_team | `GET /internal-audits/audits/{audit_id}/team-members` | `internal_audit_team.py:list_team_members` | Sí, acotada | 0 |
| internal_audit_team | `POST /internal-audits/audits/{audit_id}/team-members` | `internal_audit_team.py:create_team_member` | Sí, acotada | 0 |
| internal_audit_team | `PATCH /internal-audits/audits/{audit_id}/team-members/{team_id}` | `internal_audit_team.py:update_team_member` | Sí, acotada | 0 |
| internal_audit_team | `POST /internal-audits/audits/{audit_id}/team-members/{team_id}/withdraw` | `internal_audit_team.py:withdraw_team_member` | Sí, acotada | 0 |
| internal_audits | `POST /internal-audits/audits/{audit_id}/transition` | `internal_audits.py:transition_audit` | Sí, acotada | 0 |
| internal_audits | `GET /internal-audits/programs` | `internal_audits.py:list_programs` | Sí, acotada | 0 |
| internal_audits | `POST /internal-audits/programs` | `internal_audits.py:create_program` | Sí, acotada | 0 |
| internal_audits | `GET /internal-audits/programs/{program_id}` | `internal_audits.py:get_program` | Sí, acotada | 0 |
| internal_audits | `PATCH /internal-audits/programs/{program_id}` | `internal_audits.py:update_program` | Sí, acotada | 0 |
| internal_audits | `POST /internal-audits/programs/{program_id}/transition` | `internal_audits.py:transition_program` | Sí, acotada | 0 |
| nonconformities | `GET /nonconformities` | `nonconformities.py:list_ncrs` | Sí, acotada | 0 |
| nonconformities | `POST /nonconformities` | `nonconformities.py:create` | No; implementada sin esta observación | 0 |
| nonconformities | `GET /nonconformities/{ncr_id}` | `nonconformities.py:get_ncr` | Sí, acotada | 0 |
| nonconformities | `PATCH /nonconformities/{ncr_id}` | `nonconformities.py:update` | No; implementada sin esta observación | 0 |
| nonconformities | `POST /nonconformities/{ncr_id}/transition` | `nonconformities.py:transition` | No; implementada sin esta observación | 0 |
| ncr_links | `GET /nonconformities/{nonconformity_id}/control-links` | `ncr_links.py:list_control_links` | Sí, acotada | 0 |
| ncr_links | `POST /nonconformities/{nonconformity_id}/control-links` | `ncr_links.py:add_control_route` | No; implementada sin esta observación | 0 |
| ncr_links | `POST /nonconformities/{nonconformity_id}/control-links/{link_id}/remove` | `ncr_links.py:remove_control_route` | No; implementada sin esta observación | 0 |
| ncr_links | `GET /nonconformities/{nonconformity_id}/document-links` | `ncr_links.py:list_document_links` | Sí, acotada | 0 |
| ncr_links | `POST /nonconformities/{nonconformity_id}/document-links` | `ncr_links.py:add_document_route` | No; implementada sin esta observación | 0 |
| ncr_links | `POST /nonconformities/{nonconformity_id}/document-links/{link_id}/remove` | `ncr_links.py:remove_document_route` | No; implementada sin esta observación | 0 |
| ncr_links | `GET /nonconformities/{nonconformity_id}/evidence-links` | `ncr_links.py:list_evidence_links` | Sí, acotada | 0 |
| ncr_links | `POST /nonconformities/{nonconformity_id}/evidence-links` | `ncr_links.py:add_evidence_route` | No; implementada sin esta observación | 0 |
| ncr_links | `POST /nonconformities/{nonconformity_id}/evidence-links/{link_id}/remove` | `ncr_links.py:remove_evidence_route` | No; implementada sin esta observación | 0 |
| ncr_links | `GET /nonconformities/{nonconformity_id}/risk-links` | `ncr_links.py:list_risk_links` | Sí, acotada | 0 |
| ncr_links | `POST /nonconformities/{nonconformity_id}/risk-links` | `ncr_links.py:add_risk_route` | No; implementada sin esta observación | 0 |
| ncr_links | `POST /nonconformities/{nonconformity_id}/risk-links/{link_id}/remove` | `ncr_links.py:remove_risk_route` | No; implementada sin esta observación | 0 |
| organization | `GET /organization/assignments` | `organization.py:get_assignments` | Sí, acotada | 0 |
| organization | `POST /organization/assignments` | `organization.py:post_assignment` | No; implementada sin esta observación | 0 |
| organization | `PATCH /organization/assignments/{assignment_id}` | `organization.py:patch_assignment` | No; implementada sin esta observación | 0 |
| organization | `GET /organization/members` | `organization.py:get_members` | Sí, acotada | 0 |
| organization | `GET /organization/units` | `organization.py:get_units` | Sí, acotada | 0 |
| organization | `POST /organization/units` | `organization.py:post_unit` | Sí, acotada | 0 |
| organization | `GET /organization/units/{unit_id}` | `organization.py:get_unit` | No; implementada sin esta observación | 0 |
| organization | `PATCH /organization/units/{unit_id}` | `organization.py:patch_unit` | Sí, acotada | 0 |
| organization | `POST /organization/units/{unit_id}/archive` | `organization.py:post_archive` | No; implementada sin esta observación | 0 |
| organization | `POST /organization/units/{unit_id}/move` | `organization.py:post_move` | No; implementada sin esta observación | 0 |
| organization | `POST /organization/units/{unit_id}/restore` | `organization.py:post_restore` | No; implementada sin esta observación | 0 |
| processes | `GET /processes` | `processes.py:processes` | Sí, acotada | 0 |
| processes | `POST /processes` | `processes.py:create` | Sí, acotada | 0 |
| processes | `GET /processes/scopes` | `processes.py:scopes` | No; implementada sin esta observación | 0 |
| processes | `GET /processes/{process_id}` | `processes.py:process` | Sí, acotada | 0 |
| processes | `PATCH /processes/{process_id}` | `processes.py:update` | No; implementada sin esta observación | 0 |
| processes | `POST /processes/{process_id}/archive` | `processes.py:archive` | No; implementada sin esta observación | 0 |
| processes | `POST /processes/{process_id}/restore` | `processes.py:restore` | No; implementada sin esta observación | 0 |
| qms_access | `GET /qms-access/active-capabilities` | `qms_access.py:active_capability_summary` | No; implementada sin esta observación | 0 |
| qms_access | `GET /qms-access/effective` | `qms_access.py:effective_access` | No; implementada sin esta observación | 0 |
| qms_access | `GET /qms-access/grants` | `qms_access.py:grants` | Sí, acotada | 1 |
| qms_access | `POST /qms-access/grants` | `qms_access.py:grant` | Sí, acotada | 3 |
| qms_access | `POST /qms-access/grants/{grant_id}/revoke` | `qms_access.py:revoke` | Sí, acotada | 1 |
| risks | `GET /risks` | `risks.py:list_risks` | Sí, acotada | 0 |
| risks | `POST /risks` | `risks.py:create` | No; implementada sin esta observación | 0 |
| risks | `GET /risks/{risk_id}` | `risks.py:get_risk` | Sí, acotada | 0 |
| risks | `PATCH /risks/{risk_id}` | `risks.py:update` | No; implementada sin esta observación | 0 |
| risk_links | `GET /risks/{risk_id}/control-links` | `risk_links.py:list_control_links` | Sí, acotada | 0 |
| risk_links | `POST /risks/{risk_id}/control-links` | `risk_links.py:add_control_route` | No; implementada sin esta observación | 0 |
| risk_links | `POST /risks/{risk_id}/control-links/{link_id}/remove` | `risk_links.py:remove_control_route` | No; implementada sin esta observación | 0 |
| risk_links | `GET /risks/{risk_id}/document-links` | `risk_links.py:list_document_links` | Sí, acotada | 0 |
| risk_links | `POST /risks/{risk_id}/document-links` | `risk_links.py:add_document_route` | No; implementada sin esta observación | 0 |
| risk_links | `POST /risks/{risk_id}/document-links/{link_id}/remove` | `risk_links.py:remove_document_route` | No; implementada sin esta observación | 0 |
| risks | `POST /risks/{risk_id}/transition` | `risks.py:transition` | No; implementada sin esta observación | 0 |
| tenant | `GET /tenant/context` | `tenant.py:tenant_context` | Sí, acotada | 0 |
| workflow | `GET /workflow-instances` | `workflow.py:instances` | Sí, acotada | 0 |
| workflow | `POST /workflow-instances` | `workflow.py:start` | Sí, acotada | 0 |
| workflow | `GET /workflow-instances/{instance_id}` | `workflow.py:instance` | No; implementada sin esta observación | 0 |
| workflow | `GET /workflow-instances/{instance_id}/actions` | `workflow.py:actions` | No; implementada sin esta observación | 0 |
| workflow | `POST /workflow-instances/{instance_id}/cancel` | `workflow.py:cancel` | Sí, acotada | 0 |
| workflow | `GET /workflow-instances/{instance_id}/history` | `workflow.py:history` | Sí, acotada | 0 |
| workflow | `POST /workflow-instances/{instance_id}/transition` | `workflow.py:transition` | No; implementada sin esta observación | 0 |
| workflow | `GET /workflows` | `workflow.py:definitions` | Sí, acotada | 0 |
| workflow | `POST /workflows` | `workflow.py:create` | Sí, acotada | 0 |
| workflow | `GET /workflows/versions/{version_id}` | `workflow.py:version_detail` | No; implementada sin esta observación | 0 |
| workflow | `GET /workflows/versions/{version_id}/assignments` | `workflow.py:assignments` | Sí, acotada | 0 |
| workflow | `POST /workflows/versions/{version_id}/assignments` | `workflow.py:add_assignment` | Sí, acotada | 0 |
| workflow | `PATCH /workflows/versions/{version_id}/assignments/{assignment_id}` | `workflow.py:edit_assignment` | No; implementada sin esta observación | 0 |
| workflow | `POST /workflows/versions/{version_id}/publish` | `workflow.py:publish` | Sí, acotada | 0 |
| workflow | `GET /workflows/versions/{version_id}/steps` | `workflow.py:steps` | Sí, acotada | 0 |
| workflow | `POST /workflows/versions/{version_id}/steps` | `workflow.py:add_step` | Sí, acotada | 0 |
| workflow | `PATCH /workflows/versions/{version_id}/steps/{step_id}` | `workflow.py:edit_step` | No; implementada sin esta observación | 0 |
| workflow | `GET /workflows/versions/{version_id}/transitions` | `workflow.py:transitions` | Sí, acotada | 0 |
| workflow | `POST /workflows/versions/{version_id}/transitions` | `workflow.py:add_transition` | Sí, acotada | 0 |
| workflow | `PATCH /workflows/versions/{version_id}/transitions/{transition_id}` | `workflow.py:edit_transition` | No; implementada sin esta observación | 0 |
| workflow | `PATCH /workflows/{workflow_id}` | `workflow.py:update` | No; implementada sin esta observación | 0 |
| workflow | `GET /workflows/{workflow_id}/versions` | `workflow.py:versions` | Sí, acotada | 0 |
| workflow | `POST /workflows/{workflow_id}/versions` | `workflow.py:new_version` | Sí, acotada | 0 |
