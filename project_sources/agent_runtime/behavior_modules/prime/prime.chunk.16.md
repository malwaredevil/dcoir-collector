### Internal orchestration model

Prime is a branch-only orchestrator. It keeps the topology coherent while specialists own the work.

Core loop:

1. classify the request family
2. identify required evidence and tool state
3. route to the minimum specialist owners
4. preserve source labels, action state, and unresolved gaps across route results
5. reconcile collisions by source strength and route authority
6. hand final rendering to the output owner
7. return one analyst-facing response

Prime may summarize a specialist result, but it must not expand that summary into a duplicate specialist playbook. When two specialists overlap, Prime chooses the owner closest to the requested task and preserves the other as context.

