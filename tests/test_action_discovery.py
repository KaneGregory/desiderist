import subprocess
import sys


def test_fresh_process_registers_builtin_actions_via_loop_import():
    """Regression test: importing only desiderist.harness.loop (the real production
    import chain used by cli.py) must be enough to populate the action registry.
    Run in a fresh subprocess so no other test file's `import desiderist.actions`
    can mask a broken registration chain."""
    script = (
        "import desiderist.harness.loop\n"
        "from desiderist.actions.registry import to_tool_specs\n"
        "print(','.join(sorted(t.name for t in to_tool_specs())))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )
    names = result.stdout.strip().split(",")
    assert "communicate_with_user" in names
