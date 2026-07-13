# Issue #197 Label Migration Dry Run

- repo: malwaredevil/dcoir-collector
- collected_utc: 2026-06-03T16:32:48Z
- mode: dry-run-no-mutations
- existing_label_count: 62
- affected_item_count: 180
- warning_item_count: 133

## Create label candidates

- area:gemini-agent
- area:supabase-ircore

## Rename plan

- area:airtable-ircore -> area:supabase-ircore
- area:gemini -> area:gemini-agent

## Final keep labels

- area:collector
- area:docs
- area:gemini-agent
- area:github-repo
- area:knowledge-docs
- area:operator-tooling
- area:project-tracking
- area:repo-governance
- area:supabase-ircore
- area:validation
- area:workflows
- type:accidental
- type:bug
- type:cleanup
- type:decision
- type:enhancement
- type:idea
- type:maintenance
- type:meta
- type:planning
- type:refactor
- type:research

## Final delete labels

- administrative
- agent-instructions
- architecture
- area:airtable-ircore
- area:gemini
- blocked
- bug
- codex
- dependencies
- documentation
- duplicate
- enhancement
- gemini-agent
- github_actions
- github-actions
- good first issue
- governance
- governance-cleanup
- help wanted
- ignore
- invalid
- ircore
- mirror
- priority:P0
- priority:P1
- priority:P2
- priority:P3
- question
- source:airtable-idea
- source:airtable-work-item
- source:governed-repo
- source:mirror-initiative
- track:automation
- track:collector
- track:delivery
- track:docs
- track:governance
- track:research
- track:skills
- track:validation
- track:workflow
- wontfix

## Affected issues and PRs

| Item | Kind | Remove | Add | Warnings |
| ---: | --- | --- | --- | --- |
| #60 | Issue |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #61 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #59 | Issue |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #57 | Issue | ignore |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #58 | Issue |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #62 | Issue |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #71 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #72 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #68 | Issue |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #63 | Issue |  |  | expected exactly one area label after migration; got 0 |
| #64 | Issue |  |  | expected exactly one area label after migration; got 0 |
| #49 | PR | codex | area:repo-governance, type:maintenance |  |
| #50 | Issue |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #48 | PR | codex | area:repo-governance, type:maintenance |  |
| #46 | PR | codex | area:repo-governance, type:maintenance |  |
| #47 | PR | codex | area:repo-governance, type:maintenance |  |
| #51 | PR | dependencies, github_actions | area:github-repo, type:maintenance |  |
| #55 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #56 | Issue | governance-cleanup | area:repo-governance, type:cleanup |  |
| #54 | Issue |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #52 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #53 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #73 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #92 | Issue |  |  | expected exactly one area label after migration; got 2 |
| #93 | Issue |  |  | expected exactly one area label after migration; got 2 |
| #91 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #88 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #89 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #94 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #98 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #99 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #97 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #95 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #96 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #78 | Issue |  |  | expected exactly one area label after migration; got 2 |
| #79 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #77 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #74 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #76 | Issue | area:airtable-ircore | area:supabase-ircore |  |
| #80 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #85 | Issue |  |  | expected exactly one area label after migration; got 2 |
| #86 | Issue |  |  | expected exactly one area label after migration; got 2 |
| #84 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #81 | Issue | area:airtable-ircore | area:supabase-ircore |  |
| #83 | Issue |  |  | expected exactly one area label after migration; got 2 |
| #15 | Issue | priority:P1, track:automation, source:airtable-work-item, mirror | area:repo-governance, type:cleanup |  |
| #16 | Issue | track:workflow, priority:P2, source:airtable-work-item, mirror | area:workflows |  |
| #14 | Issue | track:workflow, priority:P1, source:airtable-work-item, mirror | area:workflows, type:maintenance |  |
| #12 | Issue | track:skills, priority:P0, source:governed-repo, mirror | area:operator-tooling, type:maintenance |  |
| #13 | Issue | track:workflow, priority:P1, source:governed-repo, mirror | area:workflows |  |
| #17 | Issue | track:docs, priority:P2, source:governed-repo, mirror | area:docs, type:maintenance |  |
| #21 | Issue | track:governance, priority:P2, source:airtable-work-item, mirror | area:repo-governance |  |
| #22 | Issue | track:governance, priority:P2, source:airtable-work-item, mirror | area:repo-governance |  |
| #20 | Issue | track:research, priority:P2, source:airtable-work-item, mirror | area:repo-governance |  |
| #18 | Issue | track:skills, priority:P2, source:governed-repo, mirror | area:operator-tooling |  |
| #19 | Issue | track:research, priority:P2, source:governed-repo, mirror | area:repo-governance, type:maintenance |  |
| #4 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #5 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #3 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #1 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #2 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #6 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #10 | Issue | track:workflow, priority:P1, source:mirror-initiative, mirror | area:workflows, type:maintenance |  |
| #11 | Issue | track:governance, priority:P1, source:mirror-initiative, mirror | area:repo-governance, type:maintenance |  |
| #9 | Issue | track:workflow, priority:P1, source:mirror-initiative, mirror | area:workflows |  |
| #7 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #8 | Issue | track:delivery, priority:P0, source:mirror-initiative, mirror | area:repo-governance, type:maintenance |  |
| #23 | Issue | track:workflow, priority:P2, source:airtable-work-item, mirror | area:workflows, type:maintenance |  |
| #38 | Issue |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #39 | Issue |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #37 | Issue |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #35 | Issue |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #36 | Issue |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #40 | Issue |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #44 | Issue |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #45 | PR | codex | area:repo-governance, type:maintenance |  |
| #43 | Issue |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #41 | Issue |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #42 | Issue |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #27 | Issue | track:governance, priority:P2, source:airtable-work-item, mirror | area:repo-governance, type:maintenance |  |
| #28 | Issue | track:docs, priority:P2, source:airtable-work-item, mirror | area:docs |  |
| #26 | Issue | track:docs, priority:P2, source:airtable-work-item, mirror | area:docs |  |
| #24 | Issue | track:research, priority:P2, source:airtable-work-item, mirror | area:repo-governance |  |
| #25 | Issue | track:governance, priority:P2, source:airtable-work-item, mirror | area:repo-governance, type:maintenance |  |
| #29 | Issue | track:governance, priority:P2, source:airtable-work-item, mirror | area:repo-governance |  |
| #33 | Issue | track:governance, priority:P2, source:airtable-work-item, mirror | area:repo-governance, type:maintenance |  |
| #34 | Issue | track:workflow, priority:P1, source:airtable-idea, mirror | area:workflows |  |
| #32 | Issue | track:docs, priority:P2, source:airtable-work-item, mirror | area:docs |  |
| #30 | Issue | track:governance, priority:P2, source:airtable-work-item, mirror | area:repo-governance, type:maintenance |  |
| #31 | Issue | track:governance, priority:P2, source:airtable-work-item, mirror | area:repo-governance, type:maintenance |  |
| #168 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #169 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #167 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #165 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #166 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #170 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #174 | Issue | gemini-agent | area:gemini-agent | expected exactly one type label after migration; got 0 |
| #175 | Issue | architecture, administrative, gemini-agent | area:gemini-agent, type:maintenance |  |
| #173 | Issue | architecture, administrative | area:repo-governance, type:maintenance |  |
| #171 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #172 | Issue | governance, ircore, agent-instructions | area:supabase-ircore, type:maintenance |  |
| #153 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #154 | Issue |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #152 | Issue | enhancement |  |  |
| #150 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #151 | Issue | enhancement |  |  |
| #155 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #163 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #164 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #161 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #157 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #159 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #176 | Issue | architecture, administrative | area:repo-governance, type:maintenance |  |
| #191 | Issue |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #192 | Issue |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #190 | Issue | area:gemini | area:gemini-agent | expected exactly one area label after migration; got 2 |
| #188 | Issue |  |  | expected exactly one area label after migration; got 2 |
| #189 | Issue |  |  | expected exactly one area label after migration; got 2 |
| #193 | Issue |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #200 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #201 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #199 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #195 | Issue |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #198 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #180 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #181 | Issue |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #179 | Issue | gemini-agent |  | expected exactly one type label after migration; got 0 |
| #177 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #178 | Issue | gemini-agent | area:gemini-agent | expected exactly one type label after migration; got 0 |
| #182 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #186 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #187 | Issue |  |  | expected exactly one area label after migration; got 2 |
| #185 | Issue |  |  | expected exactly one area label after migration; got 2 |
| #183 | PR | dependencies, github-actions | area:github-repo, type:maintenance |  |
| #184 | Issue | gemini-agent |  | expected exactly one type label after migration; got 0 |
| #115 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #116 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #114 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #112 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #113 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #117 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #123 | Issue |  |  | expected exactly one area label after migration; got 0 |
| #125 | Issue |  |  | expected exactly one area label after migration; got 2 |
| #120 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #118 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #119 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #103 | Issue | area:airtable-ircore | area:supabase-ircore | expected exactly one type label after migration; got 0 |
| #105 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #102 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #100 | Issue | area:airtable-ircore | area:supabase-ircore | expected exactly one type label after migration; got 2 |
| #101 | Issue | area:airtable-ircore | area:supabase-ircore |  |
| #106 | Issue |  |  | expected exactly one area label after migration; got 2 |
| #110 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #111 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #109 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #107 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #108 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #126 | Issue |  |  | expected exactly one area label after migration; got 2 |
| #142 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #143 | Issue | area:airtable-ircore | area:supabase-ircore |  |
| #140 | PR | enhancement | type:enhancement | expected exactly one area label after migration; got 0 |
| #139 | Issue | enhancement, area:airtable-ircore | area:supabase-ircore |  |
| #141 | Issue | enhancement | type:enhancement | expected exactly one area label after migration; got 0 |
| #144 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #148 | Issue | architecture, administrative | area:repo-governance, type:maintenance |  |
| #149 | Issue |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #147 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #145 | Issue |  |  | expected exactly one type label after migration; got 2 |
| #146 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #131 | Issue |  |  | expected exactly one area label after migration; got 2 |
| #132 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #130 | Issue |  |  | expected exactly one area label after migration; got 2 |
| #128 | Issue |  |  | expected exactly one area label after migration; got 2 |
| #129 | Issue |  |  | expected exactly one area label after migration; got 2 |
| #133 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #137 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #138 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #136 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #134 | PR |  |  | expected exactly one area label after migration; got 0; expected exactly one type label after migration; got 0 |
| #135 | Issue |  |  | expected exactly one area label after migration; got 2 |
