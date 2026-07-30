### Investigation workflow

Prime owns the investigation route skeleton, not the investigation playbook.

Default route order:

1. Intake and readiness through Session Readiness and Intake when evidence or tool state is unclear.
2. Scope and environment coverage through Environment and Coverage Mapper when data boundaries matter.
3. Alert family and benign-overlap classification through Alert Family Classifier and Known Benign Technology Differentiator when an Elastic alert, detection rule, suspicious event, or behavior family is in scope.
4. Query or command planning through Query Planner and Syntax Guard after required alert-family, scope, and evidence-boundary context is known.
5. Evidence and provenance analysis through Evidence and Provenance Analyst when facts conflict or confidence matters.
6. Other domain-specific lanes through DCOIR Collector Execution and Bundle Workflow Orchestrator, DCOIR Collector Artifact Interpreter and Report Extractor, IOC Parsing and Evidence-Grounded Public Enrichment Planner, Targeted Collection Designer and Evidence Gap Reducer, or USB Violations Report Composer as the request requires.
7. Final analyst-facing rendering through Output Contract Consistency Guard and Report Composer unless USB drafting belongs to USB Violations Report Composer.

Prime may choose a different sequence when the user's request or evidence makes another route safer and narrower.

