# Security Policy

## Supported Versions

Only the latest release version on the `main` branch of ALOS receives security updates.

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0.0 | :x:                |

## Reporting a Vulnerability

We take the security of ALOS seriously. If you discover a vulnerability or potential security risk, please **do not** open a public issue.

### Disclosure Process
1. Email your findings directly to the repository maintainer at **brandon-fox@users.noreply.github.com** or submit a private security advisory via [GitHub Security Advisories](https://github.com/brandon-fox/alos/security/advisories/new).
2. Include a detailed description of the vulnerability, steps to reproduce, and any proof-of-concept payload if available.
3. You will receive an acknowledgment within 48 hours.
4. We will keep you updated as we investigate and develop a patch.

## Security Best Practices for Self-Hosting
- **Environment Secrets**: Never commit `.env` or plain-text secrets to version control.
- **Local Vault**: Keep personal memory vault notes (`vault/`) in private local storage or a separate private repository.
- **Network Boundaries**: Ensure n8n and database instances are protected behind internal subnets or Cloudflare Tunnels.
