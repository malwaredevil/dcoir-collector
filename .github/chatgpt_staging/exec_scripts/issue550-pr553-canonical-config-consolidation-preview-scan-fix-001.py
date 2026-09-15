from pathlib import Path
p=Path('.github/chatgpt_staging/exec_scripts/issue550-pr553-canonical-config-consolidation-preview-001.py')
s=p.read_text(encoding='utf-8')
old=",('dcoir_review_required_runtime_patch_v54.py','_patch_config_loader','_patch_config_loader(module)',['LOAD_STORAGE'])"
if old not in s: raise SystemExit('v54 tuple anchor missing')
s=s.replace(old,'',1)
anchor="for rel,fs in {'dcoir_review_required_runtime_patch_v32.py'"
special='''p=scripts/'dcoir_review_required_runtime_patch_v54.py'\nremove_func(p,'_patch_config_loader')\nx=rd(p)\nfor q in (\n '        (module, "load_pareto_context_config", "module.load_pareto_context_config"),\\n',\n '        (module, LOAD_STORAGE, "module.load-storage"),\\n',\n '        "module.load_pareto_context_config": _capture_attr(module, "load_pareto_context_config"),\\n',\n '        "module.load-storage": _capture_attr(module, LOAD_STORAGE),\\n',\n '        ("config-loader", _patch_config_loader),\\n',\n):\n if q not in x: raise RuntimeError('v54 config rollback anchor missing: '+q.strip())\n x=x.replace(q,'',1)\nwr(p,x)\nremove_dead_assign(p,'LOAD_STORAGE')\n'''
if anchor not in s: raise SystemExit('helper anchor missing')
s=s.replace(anchor,special+anchor,1)
oldscan="for p in scripts.rglob('*.py'):\n x=rd(p)\n if 'def _patch_config_loader(' in x or 'def _install_config_loader(' in x or '._patch_config_loader(' in x or '._install_config_loader(' in x: raise RuntimeError('config wrapper remains '+str(p.relative_to(scripts)))"
newscan="for p in scripts.rglob('*.py'):\n if p.name == 'dcoir_review_runtime_module_loader_selftest.py': continue\n x=rd(p)\n if 'def _patch_config_loader(' in x or 'def _install_config_loader(' in x or '._patch_config_loader(' in x or '._install_config_loader(' in x: raise RuntimeError('config wrapper remains '+str(p.relative_to(scripts)))"
if oldscan not in s: raise SystemExit('preview scan anchor missing')
s=s.replace(oldscan,newscan,1)
exec(compile(s,str(p),'exec'),{'__name__':'__main__'})
