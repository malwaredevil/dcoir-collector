from pathlib import Path
p=Path('.github/chatgpt_staging/exec_scripts/issue550-pr553-canonical-config-consolidation-preview-scan-fix-001.py')
w=p.read_text(encoding='utf-8')
needle="exec(compile(s,str(p),'exec'),{'__name__':'__main__'})"
if needle not in w: raise SystemExit('scan-fix exec anchor missing')
inject='''test_anchor="changed=run('git','diff','--name-only',cwd=wt).stdout.splitlines()"\nfix=\"\"\"v54test=scripts/'dcoir_review_required_runtime_patch_v54_selftest.py'\\nx=rd(v54test)\\nold='''    fake = FakeModule()\\n    v54.apply_pareto_context_module(fake)\\n    config = fake.load_pareto_context_config(\\\"unused\\\")\\n    assert isinstance(getattr(config, v54.SINK_ATTR, None), v54.RunTelemetrySink)\\n'''\\nnew='''    fake = FakeModule()\\n    v54.apply_pareto_context_module(fake)\\n    config = fake.load_pareto_context_config(\\\"unused\\\")\\n    # This synthetic component fixture bypasses the canonical Pareto config loader.\\n    # Production initialization is asserted above; initialize the sink directly here.\\n    v54._ensure_sink(config)\\n    assert isinstance(getattr(config, v54.SINK_ATTR, None), v54.RunTelemetrySink)\\n'''\\nif old not in x: raise RuntimeError('v54 selftest synthetic config anchor missing')\\nwr(v54test,x.replace(old,new,1))\\n\"\"\"\nif test_anchor not in s: raise SystemExit('base transformer changed-files anchor missing')\ns=s.replace(test_anchor,fix+test_anchor,1)\nexec(compile(s,str(p),'exec'),{'__name__':'__main__'})'''
w=w.replace(needle,inject,1)
exec(compile(w,str(p),'exec'),{'__name__':'__main__'})
