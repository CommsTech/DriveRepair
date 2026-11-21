# Pick distribution & release channels

Type: grilling
Status: open
Blocked by: 01, 02

## Question

Given the locked audience and the research in [Distribution mechanism research](02-distribution-mechanism-research.md), pick: the primary install path (bootstrap script vs PyPI/pipx vs bundled binaries vs hybrid) and the release channels (Gitea releases; PyPI; GitHub mirror releases if/when credentials exist). Related owner context: Gitea is the trusted primary; GitHub has no agent credentials; explicit-approval policy for installing system packages (smartctl) must be preserved.
