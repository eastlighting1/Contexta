# Security Policy

## Supported Versions

Only the latest release receives security fixes.
Older versions are not actively patched.

| Version | Supported |
|---------|-----------|
| latest  | yes       |
| < latest | no       |

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report security issues by emailing the maintainers directly.
Include as much detail as possible:

- A description of the vulnerability and its potential impact
- Steps to reproduce or a minimal proof-of-concept
- Any suggested fix or mitigation you have identified

### Response timeline

| Stage | Target |
|-------|--------|
| Acknowledgement | Within 3 business days |
| Initial assessment | Within 7 business days |
| Fix or mitigation | Depends on severity (see below) |

### Severity and fix targets

| Severity | Fix target |
|----------|------------|
| Critical | Within 7 days |
| High | Within 14 days |
| Medium | Next regular release |
| Low | Scheduled at maintainer discretion |

## Scope

Contexta is a **local-first** observability library.
All data is stored on the user's own machine; there is no
cloud backend, no telemetry, and no network traffic by default.

The following are therefore **out of scope**:

- Attacks requiring physical access to the user's machine
- Vulnerabilities in optional third-party integrations
  (scikit-learn, PyTorch, Transformers, MLflow, OpenTelemetry)
  — report those to their respective projects
- Issues in example scripts under `examples/` that do not
  affect the core library

## Disclosure Policy

Once a fix is released, we will publish a brief security advisory
on the GitHub repository. We follow a **coordinated disclosure**
model: reporters are credited (with permission) in the advisory.
