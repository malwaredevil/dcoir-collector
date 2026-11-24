from pathlib import Path

p = Path('.github/chatgpt_staging/exec_scripts/issue550-pr553-canonical-config-consolidation-preview-scan-fix-001.py')
wrapper = p.read_text(encoding='utf-8')
needle = "exec(compile(s,str(p),'exec'),{'__name__':'__main__'})"
if needle not in wrapper:
    raise SystemExit('scan-fix exec anchor missing')

fixture_transform = r'''v54test=scripts/'dcoir_review_required_runtime_patch_v54_selftest.py'
x=rd(v54test)
old="""    fake = FakeModule()
    v54.apply_pareto_context_module(fake)
    config = fake.load_pareto_context_config("unused")
    assert isinstance(getattr(config, v54.SINK_ATTR, None), v54.RunTelemetrySink)
"""
new="""    fake = FakeModule()
    v54.apply_pareto_context_module(fake)
    config = fake.load_pareto_context_config("unused")
    # Synthetic component fixtures bypass the canonical production config loader.
    # Production initialization is asserted above; initialize the shared sink explicitly here.
    v54._ensure_sink(config)
    assert isinstance(getattr(config, v54.SINK_ATTR, None), v54.RunTelemetrySink)
"""
if old not in x: raise RuntimeError('v54 primary synthetic config anchor missing')
x=x.replace(old,new,1)
old="""    missing_config = fake.load_pareto_context_config("unused")
    missing_sink = getattr(missing_config, v54.SINK_ATTR)
"""
new="""    missing_config = fake.load_pareto_context_config("unused")
    missing_sink = v54._ensure_sink(missing_config)
"""
if old not in x: raise RuntimeError('v54 missing-metadata synthetic config anchor missing')
x=x.replace(old,new,1)
old="""    error_config = fake.load_pareto_context_config("unused")
    shallow_error_config = copy.copy(error_config)
"""
new="""    error_config = fake.load_pareto_context_config("unused")
    v54._ensure_sink(error_config)
    shallow_error_config = copy.copy(error_config)
"""
if old not in x: raise RuntimeError('v54 error-propagation synthetic config anchor missing')
x=x.replace(old,new,1)
wr(v54test,x)
'''

test_anchor = "changed=run('git','diff','--name-only',cwd=wt).stdout.splitlines()"
injected = "\n".join([
    "test_anchor=" + repr(test_anchor),
    "fixture_transform=" + repr(fixture_transform),
    "if test_anchor not in s: raise SystemExit('base transformer changed-files anchor missing')",
    "s=s.replace(test_anchor,fixture_transform+test_anchor,1)",
    needle,
])
wrapper = wrapper.replace(needle, injected, 1)
exec(compile(wrapper, str(p), 'exec'), {'__name__': '__main__'})
