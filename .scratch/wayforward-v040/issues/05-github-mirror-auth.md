# GitHub mirror auth decision input

Type: task
Status: open
Blocked by: 03

## Question

GitHub publishing currently has no credentials in any agent session (gh CLI reports not logged in; HTTPS push produced no output). If the channel decision includes GitHub: owner supplies auth (PAT or SSH) through the approved channel, agent verifies push and CI run start. If GitHub is dropped from v0.4.0 scope: resolve this ticket as resolved-not-needed with the reason. Record only the mechanism, never the credential values.
