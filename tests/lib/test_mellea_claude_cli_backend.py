import asyncio
import json

from mellea.backends.model_options import ModelOption
from mellea.core import CBlock, GenerateLog
from mellea.stdlib.context.simple import SimpleContext
from pydantic import BaseModel

from scripts.lib.mellea_claude_cli_backend import ClaudeCLIBackend


class _Answer(BaseModel):
    text: str


def _envelope(
    *, result: str | None = None, structured_output=None, is_error: bool = False
) -> bytes:
    body: dict = {"is_error": is_error}
    if result is not None:
        body["result"] = result
    if structured_output is not None:
        body["structured_output"] = structured_output
    return json.dumps(body).encode()


def _mock_subprocess(monkeypatch, stdout: bytes, stderr: bytes = b"", returncode: int = 0):
    """Patches asyncio.create_subprocess_exec with a fake process, and returns the mock used to
    start it so tests can assert on the argv it was called with."""

    class _FakeProcess:
        def __init__(self):
            self.returncode = returncode

        async def communicate(self):
            return stdout, stderr

    calls: list[tuple] = []

    async def _fake_create_subprocess_exec(*args, **kwargs):
        calls.append(args)
        return _FakeProcess()

    monkeypatch.setattr(
        "scripts.lib.mellea_claude_cli_backend.asyncio.create_subprocess_exec",
        _fake_create_subprocess_exec,
    )
    return calls


def test_init_sets_model_id_provider_and_budget() -> None:
    backend = ClaudeCLIBackend(model="sonnet", max_budget_usd=1.5)

    assert backend._model_id == "sonnet"
    assert backend._provider == "claude-cli"
    assert backend.max_budget_usd == 1.5
    assert backend.model_options == {}


def test_render_prompt_with_no_history_and_no_system_prompt() -> None:
    backend = ClaudeCLIBackend()

    system_prompt, user_prompt = backend._render_prompt(CBlock("hello world"), SimpleContext())

    assert system_prompt is None
    assert user_prompt == "hello world"


def test_run_claude_cli_builds_expected_command(monkeypatch) -> None:
    calls = _mock_subprocess(monkeypatch, _envelope(result="hi"))

    content = asyncio.run(
        ClaudeCLIBackend(model="sonnet", max_budget_usd=3.0)._run_claude_cli(
            "system prompt text", "user prompt text", format=None, model_options=None
        )
    )

    assert content == "hi"
    (argv,) = calls
    assert argv[:3] == ("claude", "-p", "user prompt text")
    assert "--model" in argv and argv[argv.index("--model") + 1] == "sonnet"
    assert "--max-budget-usd" in argv and argv[argv.index("--max-budget-usd") + 1] == "3.0"
    assert "--tools" in argv and argv[argv.index("--tools") + 1] == ""
    assert "--no-session-persistence" in argv
    assert (
        "--system-prompt" in argv
        and argv[argv.index("--system-prompt") + 1] == "system prompt text"
    )
    assert "--json-schema" not in argv


def test_run_claude_cli_omits_system_prompt_flag_when_none(monkeypatch) -> None:
    calls = _mock_subprocess(monkeypatch, _envelope(result="hi"))

    asyncio.run(
        ClaudeCLIBackend()._run_claude_cli(
            None, "user prompt text", format=None, model_options=None
        )
    )

    (argv,) = calls
    assert "--system-prompt" not in argv


def test_run_claude_cli_passes_json_schema_for_format(monkeypatch) -> None:
    calls = _mock_subprocess(monkeypatch, _envelope(structured_output={"text": "hi"}))

    content = asyncio.run(
        ClaudeCLIBackend()._run_claude_cli(None, "user prompt", format=_Answer, model_options=None)
    )

    assert json.loads(content) == {"text": "hi"}
    (argv,) = calls
    assert "--json-schema" in argv
    schema = json.loads(argv[argv.index("--json-schema") + 1])
    assert schema == _Answer.model_json_schema()


def test_run_claude_cli_model_options_system_prompt_overrides_argument(monkeypatch) -> None:
    calls = _mock_subprocess(monkeypatch, _envelope(result="hi"))

    asyncio.run(
        ClaudeCLIBackend()._run_claude_cli(
            "fallback",
            "user prompt",
            format=None,
            model_options={ModelOption.SYSTEM_PROMPT: "from model_options"},
        )
    )

    (argv,) = calls
    assert argv[argv.index("--system-prompt") + 1] == "from model_options"


def test_run_claude_cli_raises_on_nonzero_exit(monkeypatch) -> None:
    _mock_subprocess(monkeypatch, stdout=b"", stderr=b"boom", returncode=1)

    try:
        asyncio.run(
            ClaudeCLIBackend()._run_claude_cli(None, "user prompt", format=None, model_options=None)
        )
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "exited 1" in str(exc)
        assert "boom" in str(exc)


def test_run_claude_cli_raises_on_is_error_envelope(monkeypatch) -> None:
    _mock_subprocess(monkeypatch, _envelope(result="ignored", is_error=True))

    try:
        asyncio.run(
            ClaudeCLIBackend()._run_claude_cli(None, "user prompt", format=None, model_options=None)
        )
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "reported an error" in str(exc)


def test_generate_from_context_returns_resolved_thunk_with_generate_log(monkeypatch) -> None:
    """Regression test for the real bug this backend hit: a ModelOutputThunk returned without a
    populated _generate_log passes _generate_from_context's own contract but raises AssertionError
    the moment mellea.stdlib.functional.aact resolves it via session.instruct() - see the module
    docstring. This checks the contract directly, at the level that actually matters, instead of
    only re-deriving it by exercising the full session.instruct() plumbing."""
    _mock_subprocess(monkeypatch, _envelope(result="the answer"))
    backend = ClaudeCLIBackend(model="sonnet")
    action = CBlock("what is the answer?")

    mot, new_ctx = asyncio.run(
        backend._generate_from_context(action, SimpleContext(), format=None, model_options=None)
    )

    assert mot.is_computed()
    assert mot.value == "the answer"
    assert isinstance(mot._generate_log, GenerateLog)
    assert mot._generate_log.prompt == "what is the answer?"
    assert mot._generate_log.backend == "claude-cli::sonnet"
    assert mot._generate_log.model_output == "the answer"
    assert mot._generate_log.action is action
    assert new_ctx is not None


def test_generate_from_raw_runs_each_action_and_returns_no_usage(monkeypatch) -> None:
    responses = [_envelope(result="first"), _envelope(result="second")]
    call_index = {"n": 0}

    class _FakeProcess:
        def __init__(self, stdout: bytes):
            self.returncode = 0
            self._stdout = stdout

        async def communicate(self):
            return self._stdout, b""

    async def _fake_create_subprocess_exec(*args, **kwargs):
        stdout = responses[call_index["n"]]
        call_index["n"] += 1
        return _FakeProcess(stdout)

    monkeypatch.setattr(
        "scripts.lib.mellea_claude_cli_backend.asyncio.create_subprocess_exec",
        _fake_create_subprocess_exec,
    )

    backend = ClaudeCLIBackend()
    actions = [CBlock("question one"), CBlock("question two")]

    results, usage = asyncio.run(
        backend._generate_from_raw(actions, SimpleContext(), format=None, model_options=None)
    )

    assert usage is None
    assert len(results) == 2
    values = {r.value for r in results}
    assert values == {"first", "second"}
    for r in results:
        assert isinstance(r._generate_log, GenerateLog)
