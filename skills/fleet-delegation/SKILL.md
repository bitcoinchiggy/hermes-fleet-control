---
name: fleet-delegation
description: Assign work to a Fleet worker with delegate_worker, and report that status to the human using the worker's plain name rather than an @mention.
---

# Fleet delegation

delegate_worker remains the preferred structured primitive for assigning work to Fleet workers. Pass the Fleet worker name, the task, and an optional delegation id. Do not choose a channel, a public key, or a relay. `relay_accepted` means the relay stored the delegation. It is not worker execution and not task completion. A worker reply is evaluated in the originating human conversation and is not automatically acknowledged in the worker DM. A further instruction is a new delegate_worker call. Private Control-worker exchanges stay in the worker DM, and the human receives the evaluated result in the originating conversation.

Do not weaken Buzz mention validation. Do not add a generic message-sending tool. Do not add the worker to the current conversation just so a status @mention will pass. Control retains its other authorized tools for diagnosis, recovery, and general communication.

## Reporting back to the human

When reporting delegation or status back to the human, refer to the Fleet worker by plain name, for example operator, not @operator, unless that worker is actually a member of the current Buzz conversation and an intentional mention is required.

An @mention used by the human to identify a worker is input syntax and must not automatically be echoed as an @mention into a different Buzz conversation. The human↔Control conversation does not include the worker.

Write: Delegated to operator — relay accepted.
Do not write: Delegated to @operator — relay accepted.
