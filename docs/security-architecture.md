# Security Architecture

## Access Control

- Authentication through OIDC-compatible identity provider.
- Role-based access control for platform roles.
- Case-level authorization for analyst assignments.
- Attribute-based checks for sensitive actions such as export, deletion, public connector activation, and risk scoring.

## Roles

- `system_admin`: infrastructure and policy administration.
- `case_manager`: creates cases, assigns analysts, approves exports.
- `analyst`: collects, reviews, annotates, and reports case evidence.
- `reviewer`: approves high-impact conclusions and sensitive AI outputs.
- `auditor`: read-only access to audit logs and compliance reports.

## Audit Logging

Audit events are append-only and include:

- Actor.
- Action.
- Resource type and ID.
- Case ID.
- Request ID.
- Source IP and user agent.
- Before/after hashes for mutations.
- Export destination and report hash.
- Model and prompt template IDs for AI outputs.

## Encryption

- TLS for all service-to-service and browser traffic.
- PostgreSQL disk encryption at the volume layer.
- Object storage server-side encryption.
- Encrypted backups.
- Secrets managed through environment-specific secret stores.

## Privacy and Compliance

- Source attribution required for every data point.
- Retention policies per case.
- Data minimization for model context.
- Redaction workflow for irrelevant sensitive data.
- Legal basis captured at case creation.
- Human review before high-impact conclusions.
- Export approval workflow.

## Abuse Prevention

- Connector allowlists.
- robots.txt and rate-limit enforcement for crawlers.
- Deny private-account collection by default.
- Disable biometric identity matching unless separately reviewed and legally enabled.
- Block automated adverse decisioning.
- Require analyst justification for public records queries.

## Threat Model

Key risks:

- Unauthorized analyst access to sensitive cases.
- Poisoned public-source content influencing AI summaries.
- Overconfident model conclusions.
- Source tampering or evidence loss.
- Insecure exports.
- Credential leakage from connectors.

Controls:

- Strict case scoping.
- Citation-first AI prompts.
- Evidence hashing.
- Immutable audit logs.
- Export watermarking and approval.
- Secrets isolation and rotation.

