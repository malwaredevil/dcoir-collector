# PowerShell Surface Inventory

- Schema: `dcoir_powershell_surface_inventory_v1`
- Issue: #261
- Mode: `full`
- Source of truth: `filesystem recursive scan fallback`
- File facts policy: `text_bytes_with_line_endings_normalized_to_lf`
- Discovery command: `python project_sources/collector/tools/build_powershell_surface_inventory.py --repo-root . --json-output project_sources/collector/powershell_surface_inventory.json --markdown-output project_sources/collector/powershell_surface_inventory.md`
- JSON artifact: `project_sources/collector/powershell_surface_inventory.json`
- Validation: `pass`

