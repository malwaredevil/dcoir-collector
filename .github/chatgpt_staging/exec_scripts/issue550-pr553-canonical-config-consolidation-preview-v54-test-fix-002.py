from pathlib import Path

p = Path('.github/chatgpt_staging/exec_scripts/issue550-pr553-canonical-config-consolidation-preview-scan-fix-001.py')
wrapper = p.read_text(encoding='utf-8')
needle = "exec(compile(s,str(p),'exec'),{'__name__':'__main__'})"
if needle not in wrapper:
    raise SystemExit('scan-fix exec anchor missing')

fixture_transform = "\n".join([
    "v54test=scripts/'dcoir_review_required_runtime_patch_v54_selftest.py'",
    "x=rd(v54test)",
    "old='    fake = FakeModule()\\n    v54.apply_pareto_context_module(fake)\\n    config = fake.load_pareto_context_config(\\\"unused\\\")\\n    assert isinstance(getattr(config, v54.SINK_ATTR, None), v54.RunTelemetrySink)\\n'",
    "new='    fake = FakeModule()\\n    v54.apply_pareto_context_module(fake)\\n    config = fake.load_pareto_context_config(\\\"unused\\\")\\n    # This synthetic component fixture bypasses the canonical Pareto config loader.\\n    # Production initialization is asserted above; initialize the sink directly here.\\n    v54._ensure_sink(config)\\n    assert isinstance(getattr(config, v54.SINK_ATTR, None), v54.RunTelemetrySink)\\n'",
    "if old not in x: raise RuntimeError('v54 selftest synthetic config anchor missing')",
    "wr(v54test,x.replace(old,new,1))",
    "",
])

injected_lines = [
    "test_anchor=\"changed=run('git','diff','--name-only',cwd=wt).stdout.splitlines()\"",
    "fixture_transform=" + repr(fixture_transform),
    "if test_anchor not in s: raise SystemExit('base transformer changed-files anchor missing')",
    "s=s.replace(test_anchor,fixture_transform+test_anchor,1)",
    needle,
]
wrapper = wrapper.replace(needle, "\n".join(injected_lines), 1)
exec(compile(wrapper, str(p), 'exec'), {'__name__': '__main__'})
