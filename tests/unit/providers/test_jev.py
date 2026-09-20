from JevPR.decisions.context import ChangedFile, PullRequestContext
from JevPR.providers.jev import JevProvider


def test_jev_fallback_uses_file_count() -> None:
    provider = JevProvider(base_url=None)
    context = PullRequestContext(
        repository="octo/repo",
        number=1,
        title="test",
        author="alice",
        base_branch="main",
        head_branch="feature",
        changed_files=[ChangedFile(path="a.py", status="modified")],
    )

    decision = provider._heuristic_fallback(context)

    assert decision.level.value == "LOW"