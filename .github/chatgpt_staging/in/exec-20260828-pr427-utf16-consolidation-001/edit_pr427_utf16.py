from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{path}: expected one match, found {count} for {old[:80]!r}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


def insert_after_once(path: Path, anchor: str, addition: str) -> None:
    replace_once(path, anchor, anchor + addition)


builders = [
    Path('project_sources/agent_runtime/tools/build_openai_dcoir_analyst.py'),
    Path('project_sources/agent_runtime/tools/build_openai_usb_reporting.py'),
]

for path in builders:
    insert_after_once(
        path,
        "def _sha256(data: bytes) -> str:\n    return hashlib.sha256(data).hexdigest()\n",
        "\n\ndef _webui_character_count(value: str) -> int:\n    \"\"\"Count UTF-16 code units conservatively for browser-style WebUI limits.\"\"\"\n    return len(value.encode('utf-16-le')) // 2\n",
    )
    replace_once(
        path,
        "    elif len(text) > ceiling:\n        errors.append(f'Instructions exceed character ceiling: {len(text)} > {ceiling}')\n",
        "    else:\n        instruction_character_count = _webui_character_count(text)\n        if instruction_character_count > ceiling:\n            errors.append(\n                f'Instructions exceed character ceiling: {instruction_character_count} > {ceiling}'\n            )\n",
    )
    replace_once(
        path,
        "    description_ceiling = manifest.get('description_character_ceiling')\n    if type(description_ceiling) is not int or description_ceiling <= 0:\n        errors.append('description_character_ceiling must be a positive integer')\n    elif len(description) > description_ceiling:\n        errors.append(\n            f'Description exceeds character ceiling: {len(description)} > {description_ceiling}'\n        )\n",
        "    description_ceiling = manifest.get('description_character_ceiling')\n    description_character_count = _webui_character_count(description)\n    if type(description_ceiling) is not int or description_ceiling <= 0:\n        errors.append('description_character_ceiling must be a positive integer')\n    elif description_character_count > description_ceiling:\n        errors.append(\n            f'Description exceeds character ceiling: {description_character_count} > {description_ceiling}'\n        )\n",
    )
    replace_once(
        path,
        "        'instruction_character_count': len(instructions.decode('utf-8', errors='ignore')),\n",
        "        'instruction_character_count': _webui_character_count(\n            instructions.decode('utf-8', errors='ignore')\n        ),\n",
    )
    replace_once(
        path,
        "        'description_character_count': len(description),\n",
        "        'description_character_count': description_character_count,\n",
    )

combined = Path('project_sources/agent_runtime/tools/build_openai_gpt_deployment_release.py')
insert_after_once(
    combined,
    "def _sha256_file(path: Path) -> str:\n    return _sha256_bytes(path.read_bytes())\n",
    "\n\ndef _webui_character_count(value: str) -> int:\n    \"\"\"Count UTF-16 code units conservatively for browser-style WebUI limits.\"\"\"\n    return len(value.encode(\"utf-16-le\")) // 2\n",
)
replace_once(
    combined,
    "    if len(instructions_text) > INSTRUCTION_CHARACTER_CEILING:\n        errors.append(\n            f\"{target_id} Instructions exceed {INSTRUCTION_CHARACTER_CEILING} characters: \"\n            f\"{len(instructions_text)}\"\n        )\n    if len(description) > DESCRIPTION_CHARACTER_CEILING:\n        errors.append(\n            f\"{target_id} Description exceeds {DESCRIPTION_CHARACTER_CEILING} characters: \"\n            f\"{len(description)}\"\n        )\n\n    if package_manifest.get(\"instruction_character_count\") != len(instructions_text):\n        errors.append(f\"{target_id} package manifest instruction character count drift\")\n",
    "    instruction_character_count = _webui_character_count(instructions_text)\n    description_character_count = _webui_character_count(description)\n    if instruction_character_count > INSTRUCTION_CHARACTER_CEILING:\n        errors.append(\n            f\"{target_id} Instructions exceed {INSTRUCTION_CHARACTER_CEILING} characters: \"\n            f\"{instruction_character_count}\"\n        )\n    if description_character_count > DESCRIPTION_CHARACTER_CEILING:\n        errors.append(\n            f\"{target_id} Description exceeds {DESCRIPTION_CHARACTER_CEILING} characters: \"\n            f\"{description_character_count}\"\n        )\n\n    if package_manifest.get(\"instruction_character_count\") != instruction_character_count:\n        errors.append(f\"{target_id} package manifest instruction character count drift\")\n",
)
replace_once(
    combined,
    "    if package_manifest.get(\"description_character_count\") != len(description):\n        errors.append(f\"{target_id} package manifest description character count drift\")\n",
    "    if package_manifest.get(\"description_character_count\") != description_character_count:\n        errors.append(f\"{target_id} package manifest description character count drift\")\n",
)
replace_once(
    combined,
    "        f\"Character count: **{len(description)} / {DESCRIPTION_CHARACTER_CEILING}**\",\n",
    "        f\"Character count: **{_webui_character_count(description)} / {DESCRIPTION_CHARACTER_CEILING}**\",\n",
)
replace_once(
    combined,
    "            f\"Character count: **{len(instructions_text)} / {INSTRUCTION_CHARACTER_CEILING}**\",\n",
    "            f\"Character count: **{_webui_character_count(instructions_text)} / {INSTRUCTION_CHARACTER_CEILING}**\",\n",
)

# Individual DCOIR regression: Python len() sees 300 chars, WebUI-safe UTF-16 sees 301.
dcoir_test = Path('project_sources/agent_runtime/tests/build_openai_dcoir_analyst_selftest.py')
insert_after_once(
    dcoir_test,
    "    def test_description_character_ceiling_fails(self) -> None:\n        manifest = _read_json(self.manifest_path)\n        manifest['editor']['description'] = 'x' * (manifest['description_character_ceiling'] + 1)\n        _write_json(self.manifest_path, manifest)\n        self.assert_error_contains('Description exceeds character ceiling', check=False)\n",
    "\n    def test_non_bmp_description_uses_webui_safe_counting(self) -> None:\n        manifest = _read_json(self.manifest_path)\n        ceiling = manifest['description_character_ceiling']\n        manifest['editor']['description'] = ('x' * (ceiling - 1)) + '\U0001f600'\n        self.assertEqual(ceiling, len(manifest['editor']['description']))\n        self.assertEqual(ceiling + 1, MODULE._webui_character_count(manifest['editor']['description']))\n        _write_json(self.manifest_path, manifest)\n        self.assert_error_contains('Description exceeds character ceiling', check=False)\n",
)

usb_test = Path('project_sources/agent_runtime/tests/build_openai_usb_reporting_selftest.py')
insert_after_once(
    usb_test,
    "def test_description_character_ceiling_is_rejected() -> None:\n    td, repo = stage_repo()\n    try:\n        manifest_path = repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json'\n        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))\n        manifest['editor']['description'] = 'x' * (manifest['description_character_ceiling'] + 1)\n        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\\n', encoding='utf-8')\n        errors, _ = module.build_package(repo, manifest_path, check=True)\n        assert any('Description exceeds character ceiling' in error for error in errors), errors\n    finally:\n        td.cleanup()\n",
    "\n\ndef test_non_bmp_instruction_uses_webui_safe_counting() -> None:\n    td, repo = stage_repo()\n    try:\n        manifest_path = repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json'\n        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))\n        ceiling = manifest['instruction_character_ceiling']\n        instructions = repo / manifest['canonical_instructions_source']\n        text = ('x' * (ceiling - 1)) + '\U0001f600'\n        assert len(text) == ceiling\n        assert module._webui_character_count(text) == ceiling + 1\n        instructions.write_text(text, encoding='utf-8')\n        errors, _ = module.build_package(repo, manifest_path, check=True)\n        assert any('Instructions exceed character ceiling' in error for error in errors), errors\n    finally:\n        td.cleanup()\n",
)
replace_once(
    usb_test,
    "        test_description_character_ceiling_is_rejected,\n        test_unified_release_parity_report,\n",
    "        test_description_character_ceiling_is_rejected,\n        test_non_bmp_instruction_uses_webui_safe_counting,\n        test_unified_release_parity_report,\n",
)

combined_test = Path('project_sources/agent_runtime/tests/build_openai_gpt_deployment_release_selftest.py')
insert_after_once(
    combined_test,
    "def test_instruction_limit_fails_closed() -> None:\n    td, repo = stage_repo()\n    try:\n        package_root = repo / \"project_sources/agent_runtime/generated/packages/openai_dcoir_analyst\"\n        instructions_path = package_root / \"Instructions.md\"\n        instructions = \"x\" * (module.INSTRUCTION_CHARACTER_CEILING + 1)\n        instructions_path.write_text(instructions, encoding=\"utf-8\")\n        manifest_path = package_root / \"manifest.json\"\n        manifest = json.loads(manifest_path.read_text(encoding=\"utf-8\"))\n        manifest[\"instruction_character_count\"] = len(instructions)\n        manifest_path.write_bytes(module._json_bytes(manifest))\n        errors, report = _build(repo, \"out\")\n        assert errors\n        assert report[\"success\"] is False\n        assert any(\"Instructions exceed 8000 characters\" in error for error in errors), errors\n        assert report[\"zip_path\"] is None\n    finally:\n        td.cleanup()\n",
    "\n\ndef test_non_bmp_description_uses_webui_safe_counting() -> None:\n    td, repo = stage_repo()\n    try:\n        config_path = repo / \"project_sources/agent_runtime/generated/packages/openai_dcoir_analyst/GPT_Configuration.json\"\n        config = json.loads(config_path.read_text(encoding=\"utf-8\"))\n        config[\"description\"] = (\"x\" * (module.DESCRIPTION_CHARACTER_CEILING - 1)) + \"\U0001f600\"\n        assert len(config[\"description\"]) == module.DESCRIPTION_CHARACTER_CEILING\n        assert module._webui_character_count(config[\"description\"]) == module.DESCRIPTION_CHARACTER_CEILING + 1\n        config_path.write_bytes(module._json_bytes(config))\n        manifest_path = config_path.parent / \"manifest.json\"\n        manifest = json.loads(manifest_path.read_text(encoding=\"utf-8\"))\n        manifest[\"description_character_count\"] = module._webui_character_count(config[\"description\"])\n        manifest_path.write_bytes(module._json_bytes(manifest))\n        errors, report = _build(repo, \"out\")\n        assert errors\n        assert report[\"success\"] is False\n        assert any(\"Description exceeds 300 characters\" in error for error in errors), errors\n        assert report[\"zip_path\"] is None\n    finally:\n        td.cleanup()\n",
)
replace_once(
    combined_test,
    "        test_instruction_limit_fails_closed,\n        test_human_markdown_tracks_json_and_instructions,\n",
    "        test_instruction_limit_fails_closed,\n        test_non_bmp_description_uses_webui_safe_counting,\n        test_human_markdown_tracks_json_and_instructions,\n",
)

print('Applied bounded UTF-16 WebUI count hardening to PR #427 sources/tests.')
