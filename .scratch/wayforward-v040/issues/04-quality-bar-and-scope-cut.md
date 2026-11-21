# Quality bar & scope cut

Type: grilling
Status: open
Blocked by: 01

## Question

Confirm the adoption-hardening checklist and scope cut for v0.4.0: (a) run a dead-code scan (vulture/ruff) and TODO audit to zero; (b) verify tests assert behavior — add tooling or targeted fixes where tests only check line existence; (c) fresh independent review pass by a separate agent under the Codecraft gate; (d) pause native macOS write support until the distribution bridge ships; (e) define "pristine formatting/organization" concretely (formatter config committed, CI-enforced). Owner confirms the list is the bar, or amends it.
