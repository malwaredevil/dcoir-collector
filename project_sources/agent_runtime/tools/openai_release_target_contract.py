#!/usr/bin/env python3
"""Bind manual OpenAI release checks to governed source and Knowledge manifests."""
from __future__ import annotations

from typing import Any

SOURCE_SCHEMA = 'dcoir.agent_runtime.source_contract.v1'
KNOWLEDGE_SCHEMA = 'dcoir.agent_runtime.knowledge_projection.v1'


def bind_release_targets(
    source: dict[str, Any],
    projection: dict[str, Any],
    target_templates: tuple[dict[str, Any], ...],
    errors: list[str],
) -> tuple[dict[str, Any], ...]:
    """Return strict per-target runtime/Knowledge metadata; never infer defaults.

    The release's delivery names and paths remain immutable templates, while
    the runtime model and projection count must come from both governed inputs.
    """
    if source.get('schema') != SOURCE_SCHEMA:
        errors.append('OpenAI release source contract schema drift')
    if projection.get('schema') != KNOWLEDGE_SCHEMA:
        errors.append('OpenAI release Knowledge projection schema drift')

    source_items = source.get('targets')
    projection_items = projection.get('targets')
    source_ids = source.get('target_ids')
    shared_groups = source.get('knowledge_projection_groups')
    if not isinstance(shared_groups, list) or not all(isinstance(g, dict) for g in shared_groups):
        errors.append('OpenAI release shared Knowledge groups must be an array of objects')
        shared_groups = []
    if not isinstance(source_items, list) or not all(isinstance(x, dict) for x in source_items):
        errors.append('OpenAI release source targets must be an array of objects')
        source_items = []
    if not isinstance(source_ids, list) or not all(isinstance(x, str) for x in source_ids):
        errors.append('OpenAI release source target_ids must be an array of strings')
        source_ids = []
    if len(source_ids) != len(set(source_ids)):
        errors.append('OpenAI release source target_ids must be unique')
    if not isinstance(projection_items, dict):
        errors.append('OpenAI release Knowledge projection targets must be an object')
        projection_items = {}

    source_policy = source.get('knowledge_projection_policy')
    policy_limit = source_policy.get('strict_file_count_ceiling') if isinstance(source_policy, dict) else None
    projection_limit = projection.get('strict_file_count_ceiling')
    if type(policy_limit) is not int or policy_limit < 1 or (
        type(projection_limit) is not int or projection_limit != policy_limit
    ):
        errors.append('OpenAI release Knowledge file ceilings disagree or are invalid')
        policy_limit = 0

    specs = []
    for target in target_templates:
        target_id = target['target_id']
        matching = [item for item in source_items if item.get('id') == target_id]
        if target_id not in source_ids or len(matching) != 1:
            errors.append(f'{target_id} must appear exactly once in governed source targets')
            continue
        source_target = matching[0]
        if source_target.get('provider') != 'openai_webui_bedrock_hosted':
            errors.append(f'{target_id} source provider is not the governed OpenAI WebUI provider')
        model = source_target.get('runtime_model')
        if (
            not isinstance(model, str) or not model.strip()
            or model != model.strip() or len(model) > 128 or not model.isprintable()
        ):
            errors.append(f'{target_id} source runtime model is missing or invalid')

        knowledge_target = projection_items.get(target_id)
        if not isinstance(knowledge_target, dict):
            errors.append(f'{target_id} lacks a governed Knowledge projection target')
            continue
        if knowledge_target.get('mode') != 'consolidated_projection':
            errors.append(f'{target_id} must have consolidated Knowledge projections')
        count = knowledge_target.get('expected_projection_count')
        groups = knowledge_target.get('projection_groups')
        if type(count) is not int or count < 1 or count > policy_limit:
            errors.append(f'{target_id} Knowledge projection count is invalid or exceeds ceiling')
            continue
        if not isinstance(groups, list) or len(groups) != count or not all(
            isinstance(item, dict) for item in groups
        ):
            errors.append(f'{target_id} Knowledge projection count/group mismatch')
            continue
        orders = [group.get('order') for group in groups]
        if orders != list(range(count)) or not all(type(order) is int for order in orders):
            errors.append(f'{target_id} Knowledge projection group order is not contiguous')
        group_ids = [group.get('id') for group in groups]
        if not all(isinstance(value, str) and value.strip() for value in group_ids):
            errors.append(f'{target_id} Knowledge projection group ids must be nonempty strings')
        elif len(set(group_ids)) != count:
            errors.append(f'{target_id} Knowledge projection group ids must be unique')
        source_group_ids = [
            item.get('id') for item in shared_groups if item.get('target_id') == target_id
        ]
        if source_group_ids != group_ids:
            errors.append(f'{target_id} cross-manifest Knowledge projection group drift')
        specs.append({**target, 'runtime_model': model, 'knowledge_count': count})

    return tuple(specs) if not errors and len(specs) == len(target_templates) else ()
