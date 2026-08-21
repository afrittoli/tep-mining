#!/usr/bin/env python3
# Copyright 2026 The Tekton Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""A mellea Backend that drives Claude through the `claude` CLI's `-p` mode.

mellea ships backends for ollama/hf/openai/watsonx/litellm (see mellea.stdlib.session.
start_session's backend_name literal). litellm can reach Claude, but only through Anthropic API
billing - it has no path to a Claude Pro/Max subscription's included usage. classify_llm.py's
--backend claude-cli gets that included usage by shelling out to `claude -p ...` instead (see
its module docstring); this backend lets that same path go through mellea's typed/validated
`format=<pydantic model>` response handling, the way --backend mellea already does for Ollama.

mellea's own Backend abc (mellea.core.backend) is explicitly designed for exactly this: a
third-party Backend subclass is a first-class extension point, not a workaround. Claude CLI's `-p
--output-format json` mode is a single blocking call, not a token stream, so this backend
resolves the whole response before returning, as an already-computed ModelOutputThunk, rather
than building the lazy/streaming resolution machinery mellea.backends.ollama.OllamaModelBackend
needs for its actually-streaming chat endpoint. mellea.backends.dummy.DummyBackend looks like a
simpler reference for this ("just construct ModelOutputThunk(value=...) and return") but is
incomplete: every real backend (ollama.py, openai.py, litellm.py, watsonx.py, huggingface.py)
also explicitly builds a GenerateLog and assigns it to `mot._generate_log` before returning -
mellea.stdlib.functional.aact asserts `result._generate_log is not None` after resolving the
thunk, so a hand-built thunk without one raises AssertionError as soon as it goes through
session.instruct() rather than a bare backend.generate_from_context() call. Confirmed by actually
running this backend end-to-end against Claude, not just by reading DummyBackend's docstring.

Usage (mirrors mellea.start_session, but start_session's backend_name is a closed literal that
doesn't include this backend, so construct it directly and hand it to MelleaSession):

    from mellea.stdlib.session import MelleaSession
    from lib.mellea_claude_cli_backend import ClaudeCLIBackend  # scripts/ is on sys.path[0]

    session = MelleaSession(ClaudeCLIBackend(model="sonnet", max_budget_usd=2.0))
    result = session.instruct("...", format=SomePydanticModel)
"""

import asyncio
import datetime
import json
from collections.abc import Sequence
from typing import Any

from mellea.backends.model_options import ModelOption
from mellea.core import (
    Backend,
    BaseModelSubclass,
    C,
    CBlock,
    Component,
    Context,
    GenerateLog,
    ModelOutputThunk,
)
from mellea.formatters import ChatFormatter, TemplateFormatter


class ClaudeCLIBackend(Backend):
    """Runs `claude -p ... --output-format json --json-schema ...` per generation.

    Args:
        model: Claude CLI model name (e.g. "sonnet").
        max_budget_usd: Passed to `claude -p --max-budget-usd` as a per-call safety cap.
        formatter: Renders mellea's Context/Component tree into chat messages. Defaults to
            `TemplateFormatter`, the same default `OllamaModelBackend` uses.

    Raises:
        FileNotFoundError: If the `claude` executable isn't on PATH (checked at first call,
            not at construction, so building a session doesn't require Claude CLI to be
            installed if that session ends up only using other backends).
    """

    def __init__(
        self,
        model: str = "sonnet",
        max_budget_usd: float = 2.0,
        formatter: ChatFormatter | None = None,
    ):
        self.formatter: ChatFormatter = formatter or TemplateFormatter(model_id=model)
        self.model_options: dict = {}
        self._model_id: str = model
        self._provider: str = "claude-cli"
        self.max_budget_usd = max_budget_usd

    def _render_prompt(
        self, action: Component[C] | CBlock | ModelOutputThunk, ctx: Context
    ) -> tuple[str | None, str]:
        """Turns the linearized context + action into (system_prompt, user_prompt) - the same
        two-string shape _call_claude_cli already takes, so nothing downstream of the backend
        needs to change. Claude CLI's `-p` takes one flat prompt string, not a messages array,
        so non-system messages are joined with blank lines; in this pipeline's actual usage
        (classify_llm.py's mellea backend calls session.instruct() once per batch, no chat
        history) there's always exactly one non-system message and this join is a no-op."""
        linearized_context = ctx.view_for_generation()
        assert linearized_context is not None, (
            "Cannot generate from a non-linear context in a FormatterBackend."
        )
        messages = self.formatter.to_chat_messages(linearized_context)
        messages.extend(self.formatter.to_chat_messages([action]))

        model_opts = {**self.model_options}
        system_prompt = model_opts.get(ModelOption.SYSTEM_PROMPT)
        user_parts = [self.formatter.print(m) for m in messages]
        return system_prompt, "\n\n".join(user_parts)

    async def _run_claude_cli(
        self,
        system_prompt: str | None,
        user_prompt: str,
        format: type[BaseModelSubclass] | None,
        model_options: dict | None,
    ) -> str:
        model_opts = {**self.model_options, **(model_options or {})}
        system_prompt = model_opts.get(ModelOption.SYSTEM_PROMPT, system_prompt)
        max_budget_usd = model_opts.get("max_budget_usd", self.max_budget_usd)

        cmd = [
            "claude",
            "-p",
            user_prompt,
            "--output-format",
            "json",
            "--tools",
            "",
            "--no-session-persistence",
            "--model",
            self._model_id,
            "--max-budget-usd",
            str(max_budget_usd),
        ]
        if format is not None:
            cmd += ["--json-schema", json.dumps(format.model_json_schema())]
        if system_prompt is not None:
            cmd += ["--system-prompt", system_prompt]

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"claude -p exited {proc.returncode}\nstderr: {stderr.decode(errors='replace')}"
            )
        envelope = json.loads(stdout)
        if envelope.get("is_error"):
            raise RuntimeError(f"claude -p reported an error: {envelope}")

        if format is not None:
            # `structured_output` is already a parsed dict/list; mellea expects ModelOutputThunk
            # to carry the raw text so downstream code can call format.model_validate_json(...)
            # on it, the same contract OllamaModelBackend's response text satisfies.
            return json.dumps(envelope["structured_output"])
        return envelope["result"]

    def _generate_log(
        self, prompt: str, action, model_opts: dict, mot: ModelOutputThunk
    ) -> GenerateLog:
        log = GenerateLog()
        log.prompt = prompt
        log.backend = f"claude-cli::{self._model_id}"
        log.date = datetime.datetime.now()
        log.model_options = model_opts
        log.model_output = mot.value
        log.action = action
        return log

    async def _generate_from_context(
        self,
        action: Component[C] | CBlock | ModelOutputThunk,
        ctx: Context,
        *,
        format: type[BaseModelSubclass] | None = None,
        model_options: dict | None = None,
        tool_calls: bool = False,
    ) -> tuple[ModelOutputThunk[C], Context]:
        """Generate a completion for `action` given `ctx` via one blocking `claude -p` call.

        Args:
            action: The component to generate from.
            ctx: The current generation context (must be linear - see `Context.view_for_generation`).
            format: Optional pydantic model; passed to `--json-schema` as `format.model_json_schema()`.
            model_options: Per-call model options. Only `ModelOption.SYSTEM_PROMPT` is read here;
                temperature and other sampling controls have no `claude -p` equivalent (same
                limitation classify_llm.py's `_call_claude_cli` already documents) and are ignored.
            tool_calls: Not supported; `claude -p` is invoked with `--tools ""`.

        Returns:
            A resolved (already-computed) `ModelOutputThunk` holding the response text, and the
            context extended with `action` and the output.

        Raises:
            RuntimeError: If `claude -p` exits non-zero or reports `is_error` in its envelope.
        """
        await self.do_generate_walk(action)
        if tool_calls:
            from mellea.core import MelleaLogger

            MelleaLogger.get_logger().warning(
                "ClaudeCLIBackend does not support tool calling (claude -p runs with --tools "
                "''); ignoring tool_calls=True."
            )

        system_prompt, user_prompt = self._render_prompt(action, ctx)
        content = await self._run_claude_cli(system_prompt, user_prompt, format, model_options)

        mot = ModelOutputThunk(value=content)
        mot._generate_log = self._generate_log(
            user_prompt, action, {**self.model_options, **(model_options or {})}, mot
        )
        return mot, ctx.add(action).add(mot)

    async def _generate_from_raw(
        self,
        actions: Sequence[Component[C] | CBlock],
        ctx: Context,
        *,
        format: type[BaseModelSubclass] | None = None,
        model_options: dict | None = None,
        tool_calls: bool = False,
    ) -> tuple[list[ModelOutputThunk], dict[str, Any] | None]:
        """Generate one completion per action, context-free, running the `claude -p` calls
        concurrently (mirrors OllamaModelBackend's `_generate_from_raw`, which does the same for
        Ollama's non-batching completion endpoint). `claude -p --max-budget-usd` caps each call
        individually, so concurrency doesn't change the per-run budget semantics.

        Returns:
            `(results, None)` - `claude -p`'s envelope has no token-usage field in the shape
            `Backend._generate_from_raw`'s docstring expects (OpenAI-shaped aggregate usage), so
            usage is left `None`, same as `DummyBackend`.
        """
        if tool_calls:
            from mellea.core import MelleaLogger

            MelleaLogger.get_logger().warning(
                "ClaudeCLIBackend does not support tool calling (claude -p runs with --tools "
                "''); ignoring tool_calls=True."
            )
        await self.do_generate_walks(list(actions))

        async def _one(action: Component[C] | CBlock) -> ModelOutputThunk:
            prompts = [self.formatter.print(a) for a in self.formatter.to_chat_messages([action])]
            user_prompt = "\n\n".join(prompts)
            model_opts = {**self.model_options, **(model_options or {})}
            system_prompt = model_opts.get(ModelOption.SYSTEM_PROMPT)
            content = await self._run_claude_cli(system_prompt, user_prompt, format, model_options)
            mot = ModelOutputThunk(value=content)
            mot._generate_log = self._generate_log(user_prompt, action, model_opts, mot)
            return mot

        results = await asyncio.gather(*(_one(a) for a in actions))
        return list(results), None
