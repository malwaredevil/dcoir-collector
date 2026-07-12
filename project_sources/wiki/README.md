# DCOIR Knowledge to GitHub Wiki publishing

This folder documents the DCOIR GitHub Actions workflow that publishes the maintained `knowledge/` folder to the GitHub Wiki repository.

## Source model

- Maintained source: `knowledge/`
- Wiki target: `DCOIR-Collector/dcoir-collector.wiki.git`
- Workflow file: `.github/workflows/publish_knowledge_to_wiki.yml`
- Required repository secret: `DCOIR_WIKI_PUSH_TOKEN`

## Behavior

The workflow runs when changes land on `main` under `knowledge/**` or when the workflow is manually dispatched.

The workflow:

1. Checks out the normal code repository.
2. Verifies that `knowledge/README.md` exists.
3. Verifies that maintained `Knowledge - *.md` files exist.
4. Clones the separate wiki repository into `tmp_wiki`.
5. Mirrors `knowledge/` into the wiki repository.
6. Copies `knowledge/README.md` to `Home.md` for the wiki landing page.
7. Commits and pushes only when wiki content changed.

## Important safety notes

- Do not store the token in chat, external databases, screenshots, repo files, logs, or bundles.
- The repository secret name must be exactly `DCOIR_WIKI_PUSH_TOKEN`.
- The wiki must be initialized with at least one page before the workflow runs.
- The wiki is intended to mirror the maintained `knowledge/` folder. Do not manually maintain separate wiki-only operational guidance unless that is an intentional exception.

## Landing-page boundary rule

`knowledge/README.md` is mirrored to the wiki `Home.md` page and should stay focused on maintained-knowledge orientation.

Do not place builder/operator maintenance checklists or synchronization instructions in `knowledge/README.md`. Keep those instructions in operator/build-facing GitHub docs such as this file and `project_sources/gemini/bundle_source/README.md`.
