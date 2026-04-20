"""Base agent class for djgent."""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from dataclasses import asdict, is_dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Type,
    Union,
)

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)

from djgent.exceptions import AgentError
from djgent.llm.providers import get_llm
from djgent.memory.store import memory_store
from djgent.runtime import (
    AgentExecutionState,
    AgentMiddleware,
    AgentResult,
    ApprovalRequiredError,
    DynamicPromptMiddleware,
    ExecutionContext,
    OutputGuardrailMiddleware,
    StateStore,
    ToolApprovalMiddleware,
    build_langchain_middleware,
    resolve_langchain_middleware_config,
)
from djgent.runtime.mcp import load_mcp_tools
from djgent.runtime.middleware import (
    apply_after_run,
    apply_after_tool,
    apply_before_run,
    apply_before_tool,
)
from djgent.runtime.schemas import schema_name
from djgent.tools.base import Tool
from djgent.tools.registry import ToolRegistry
from djgent.utils.usage import extract_usage_details

if TYPE_CHECKING:
    from djgent.agents.multi_agent import MultiAgent


class Agent:
    """
    Main agent class for djgent.

    Agents use LLMs, middleware, and tools to accomplish tasks.
    """

    def __init__(
        self,
        name: str,
        llm: Optional[BaseLanguageModel] = None,
        tools: Optional[List[Union[str, Tool, Callable, Any]]] = None,
        memory: bool = True,
        memory_backend: str = "memory",
        conversation_id: Optional[str] = None,
        conversation_name: Optional[str] = None,
        user: Optional[Any] = None,
        system_prompt: Optional[str] = None,
        middleware: Optional[List[AgentMiddleware]] = None,
        response_schema: Optional[Type[Any]] = None,
        thread_id: Optional[str] = None,
        **kwargs: Any,
    ):
        self.name = name
        self.llm = llm
        self.memory = memory
        self.memory_backend_type = memory_backend
        self.system_prompt = system_prompt
        self.response_schema = response_schema
        self.thread_id = thread_id
        self._config = kwargs
        self.llm_identifier = kwargs.get("llm_identifier")
        self._langchain_middleware_config = resolve_langchain_middleware_config(
            kwargs.get("langchain_middleware")
        )
        self._langchain_checkpointer = kwargs.get("checkpointer")
        self._memory_init_kwargs = {
            "backend": memory_backend,
            "conversation_id": conversation_id,
            "conversation_name": conversation_name,
            "user": user,
        }
        self._message_history: List[BaseMessage] = []
        self._memory_backend = None
        self._middleware = self._build_middleware(middleware)
        self._last_result: Optional[AgentResult] = None

        if memory:
            self._init_memory_backend(
                backend=memory_backend,
                conversation_id=conversation_id,
                conversation_name=conversation_name,
                user=user,
            )

        self._state_store = StateStore(self._memory_backend)
        self.tools = self._process_tools(tools or [])

    def _build_middleware(
        self,
        middleware: Optional[List[AgentMiddleware]] = None,
    ) -> List[AgentMiddleware]:
        """Compose the default runtime middleware stack."""
        stack: List[AgentMiddleware] = [
            DynamicPromptMiddleware(),
            ToolApprovalMiddleware(),
            OutputGuardrailMiddleware(),
        ]
        stack.extend(middleware or [])
        return stack

    def _build_langchain_runtime(
        self,
    ) -> tuple[List[Any], Optional[Any]]:
        """Build LangChain built-in middleware and checkpointer options."""
        middleware, configured_checkpointer = build_langchain_middleware(
            config=self._langchain_middleware_config,
        )
        return (
            middleware,
            self._langchain_checkpointer or configured_checkpointer,
        )

    def _init_memory_backend(
        self,
        backend: str = "memory",
        conversation_id: Optional[str] = None,
        conversation_name: Optional[str] = None,
        user: Optional[Any] = None,
    ) -> None:
        from djgent.memory import get_memory_backend

        self._memory_backend = get_memory_backend(
            backend=backend,
            agent_name=self.name,
            conversation_id=conversation_id,
            conversation_name=conversation_name,
            user=user,
        )
        self._memory_backend.initialize()

        if conversation_id or (backend == "memory"):
            self._message_history = (
                self._memory_backend.get_messages_as_langchain()
            )

    def _ensure_memory_backend(self) -> bool:
        """Lazily create and initialize the configured memory backend."""
        if not self.memory:
            return False

        if self._memory_backend is None:
            self._init_memory_backend(**self._memory_init_kwargs)

        if self._memory_backend and not getattr(
            self._memory_backend, "_initialized", False
        ):
            self._memory_backend.initialize()

        return self._memory_backend is not None

    def _process_tools(
        self, tools: List[Union[str, Tool, Callable, Any]]
    ) -> List[Any]:
        """Normalize tool definitions into instances or compatible tool objects."""
        processed: List[Any] = []
        for tool in tools:
            if isinstance(tool, str):
                processed.append(ToolRegistry.get_tool_instance(tool))
            elif isinstance(tool, Tool):
                processed.append(tool)
            elif callable(tool) and not hasattr(tool, "invoke"):
                from djgent.tools.decorators import _FunctionTool

                processed.append(_FunctionTool(tool))
            else:
                processed.append(tool)
        return processed

    def _resolve_thread_id(self) -> str:
        """Resolve the active durable thread identifier."""
        if self.thread_id:
            return self.thread_id
        if self._memory_backend and self._memory_backend.conversation_id:
            self.thread_id = str(self._memory_backend.conversation_id)
            return self.thread_id
        self.thread_id = f"{self.name}:{uuid.uuid4()}"
        return self.thread_id

    def _initialize_memory_for_run(self) -> None:
        """Ensure persistent backends have an active conversation before execution."""
        if not self._ensure_memory_backend():
            return

        if self._memory_backend.conversation_id:
            self.thread_id = str(self._memory_backend.conversation_id)

    def _build_execution_context(
        self,
        input: str,
        context: Optional[Dict[str, Any]] = None,
        thread_id: Optional[str] = None,
    ) -> ExecutionContext:
        """Create the per-run execution context."""
        active_thread_id = thread_id or self._resolve_thread_id()
        durable_state = self._state_store.load(active_thread_id)
        execution = ExecutionContext(
            agent_name=self.name,
            thread_id=active_thread_id,
            input=input,
            context=dict(context or {}),
            state=durable_state.to_dict(),
        )
        execution.context.setdefault("risky_tools", self._risky_tool_map())
        execution.context.setdefault(
            "approved_tools", durable_state.values.get("approved_tools", {})
        )
        return execution

    def _risky_tool_map(self) -> Dict[str, Dict[str, Any]]:
        """Return tool approval requirements indexed by tool name."""
        data: Dict[str, Dict[str, Any]] = {}
        for tool in self.tools:
            if isinstance(tool, Tool):
                config = tool.get_tool_config()
                if config.get("requires_approval"):
                    data[config["name"]] = config
        return data

    def _build_messages(
        self, input: str, execution: ExecutionContext
    ) -> List[BaseMessage]:
        """Assemble the message list for the LLM."""
        messages: List[BaseMessage] = []

        if self.system_prompt:
            messages.append(SystemMessage(content=self.system_prompt))

        dynamic_prompt = execution.metadata.get("dynamic_prompt")
        if dynamic_prompt:
            messages.append(SystemMessage(content=dynamic_prompt))

        if self.memory:
            messages.extend(self._message_history)

        messages.append(HumanMessage(content=input))
        return messages

    def _prepare_langchain_tools(
        self, execution: ExecutionContext
    ) -> List[Any]:
        """Convert Djgent tools into LangChain-compatible wrappers."""
        lc_tools = []

        def before_tool(tool_name: str, arguments: Dict[str, Any]) -> None:
            execution.emit("tool.start", tool=tool_name, arguments=arguments)
            apply_before_tool(self._middleware, execution, tool_name, arguments)

        def after_tool(tool_name: str, result: Any) -> Any:
            result = apply_after_tool(
                self._middleware, execution, tool_name, result
            )
            execution.emit("tool.end", tool=tool_name, result=result)
            return result

        for tool in self.tools:
            if isinstance(tool, Tool):
                lc_tools.append(
                    tool.to_langchain(
                        before_tool=before_tool,
                        after_tool=after_tool,
                    )
                )
            else:
                lc_tools.append(tool)

        return lc_tools

    def _invoke_model(
        self,
        messages: List[BaseMessage],
        execution: ExecutionContext,
        **kwargs: Any,
    ) -> Any:
        """Invoke the underlying model or tool-aware agent."""
        if not self.llm:
            raise ValueError(
                "LLM not configured. Provide an LLM when creating the agent."
            )

        lc_tools = self._prepare_langchain_tools(execution)
        model_kwargs = dict(kwargs)
        langchain_middleware, checkpointer = self._build_langchain_runtime()

        if (
            self.response_schema
            and hasattr(self.llm, "with_structured_output")
            and not lc_tools
            and not langchain_middleware
        ):
            execution.emit(
                "model.structured",
                schema=schema_name(self.response_schema),
            )
            try:
                structured_llm = self.llm.with_structured_output(
                    self.response_schema
                )
            except NotImplementedError:
                execution.emit(
                    "model.structured_fallback", reason="native_not_supported"
                )
            else:
                return structured_llm.invoke(messages, **model_kwargs)

        if lc_tools or langchain_middleware or checkpointer is not None:
            from langchain.agents import create_agent

            create_kwargs: Dict[str, Any] = {
                "model": self.llm,
                "tools": lc_tools,
            }
            if langchain_middleware:
                create_kwargs["middleware"] = langchain_middleware
            if checkpointer is not None:
                create_kwargs["checkpointer"] = checkpointer
            if self.response_schema is not None:
                create_kwargs["response_format"] = self.response_schema

            try:
                agent = create_agent(**create_kwargs)
            except TypeError:
                if langchain_middleware or checkpointer is not None:
                    raise AgentError(
                        "Configured LangChain built-in middleware requires a "
                        "LangChain version with create_agent(..., middleware=..., "
                        "checkpointer=...)."
                    )
                agent = create_agent(self.llm, lc_tools)

            config = {"configurable": {"thread_id": execution.thread_id}}
            try:
                return agent.invoke(
                    {"messages": messages},
                    config=config,
                    context=execution.context,
                    **model_kwargs,
                )
            except TypeError:
                return agent.invoke({"messages": messages}, **model_kwargs)

        return self.llm.invoke(messages, **model_kwargs)

    def _normalize_agent_output(
        self, result: Any
    ) -> tuple[str, Optional[Any], List[Any]]:
        """Normalize model results into text, structured payload, and messages."""
        structured_response = None
        output_messages: List[Any] = []

        if isinstance(result, dict):
            output_messages = list(result.get("messages", []))
            if "structured_response" in result:
                structured_response = result.get("structured_response")
            if "output" in result and isinstance(result["output"], str):
                return result["output"], structured_response, output_messages
            if output_messages:
                last = output_messages[-1]
                if isinstance(last, AIMessage):
                    return (
                        str(last.content or ""),
                        structured_response,
                        output_messages,
                    )
            return (
                json.dumps(result, default=str),
                structured_response,
                output_messages,
            )

        if isinstance(result, AIMessage):
            return str(result.content or ""), None, [result]

        if self.response_schema and result is not None:
            structured_response = result
            if hasattr(result, "model_dump_json"):
                return result.model_dump_json(), structured_response, []
            if is_dataclass(result):
                return json.dumps(asdict(result)), structured_response, []
            if isinstance(result, dict):
                return json.dumps(result), structured_response, []

        return str(result), structured_response, output_messages

    def _extract_json_object(self, text: str) -> Optional[Any]:
        """Extract the first JSON object or array from text."""
        text = text.strip()
        if not text:
            return None

        try:
            return json.loads(text)
        except Exception:
            pass

        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if not match:
            return None

        try:
            return json.loads(match.group(1))
        except Exception:
            return None

    def _coerce_structured_output(
        self, output: str, schema: Optional[Type[Any]]
    ) -> Optional[Any]:
        """Validate a text output against the requested schema when possible."""
        schema = schema or self.response_schema
        if not schema:
            return None

        payload = self._extract_json_object(output)
        if payload is None:
            return None

        if hasattr(schema, "model_validate"):
            return schema.model_validate(payload)

        if hasattr(schema, "__dataclass_fields__"):
            return schema(**payload)

        try:
            return schema(**payload)
        except Exception:
            return payload

    def _update_history(
        self,
        input: str,
        output: str,
        *,
        thread_id: Optional[str] = None,
        usage_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Persist in-memory and backend chat history."""
        if not self.memory:
            return

        self._message_history.append(HumanMessage(content=input))
        self._message_history.append(AIMessage(content=str(output)))
        if self._ensure_memory_backend():
            self._memory_backend.add_message(
                "human",
                input,
                thread_id=thread_id,
            )
            ai_metadata: Dict[str, Any] = {"thread_id": thread_id}
            if usage_details:
                ai_metadata.update(
                    {
                        "input_tokens": usage_details.get("input_tokens", 0),
                        "output_tokens": usage_details.get("output_tokens", 0),
                        "total_tokens": usage_details.get("total_tokens", 0),
                        "estimated_cost": str(
                            usage_details.get("estimated_cost", "0")
                        ),
                        "model_name": usage_details.get("model_name"),
                        "llm_identifier": usage_details.get("llm_identifier"),
                        "usage_metadata": usage_details.get(
                            "usage_metadata", {}
                        ),
                        "response_metadata": usage_details.get(
                            "response_metadata", {}
                        ),
                    }
                )
            self._memory_backend.add_message("ai", str(output), **ai_metadata)

    def _persist_execution_state(
        self,
        execution: ExecutionContext,
        *,
        output: str,
        approval_error: Optional[ApprovalRequiredError] = None,
    ) -> None:
        """Save durable thread state for resuming execution."""
        history = execution.state.get("history", [])
        history.append({"role": "human", "content": execution.input})

        if approval_error:
            execution.state["status"] = "waiting_for_approval"
            execution.state["paused_tool_name"] = (
                approval_error.request.tool_name
            )
            execution.state["paused_tool_arguments"] = (
                approval_error.request.arguments
            )
            execution.state["last_output"] = approval_error.request.reason
        else:
            history.append({"role": "ai", "content": output})
            execution.state["status"] = "completed"
            execution.state["paused_tool_name"] = None
            execution.state["paused_tool_arguments"] = {}
            execution.state["last_output"] = output

        execution.state["history"] = history[-50:]
        self._state_store.save(
            AgentExecutionState.from_dict(
                execution.state,
                thread_id=execution.thread_id,
            )
        )

    def _persist_failed_run(
        self,
        input: str,
        message: str,
        *,
        role: str = "system",
        thread_id: Optional[str] = None,
    ) -> None:
        """Persist a failed or interrupted run to conversation history."""
        if not self.memory:
            return

        self._message_history.append(HumanMessage(content=input))
        if role == "ai":
            self._message_history.append(AIMessage(content=message))
        else:
            self._message_history.append(SystemMessage(content=message))

        if self._ensure_memory_backend():
            self._memory_backend.add_message(
                "human",
                input,
                thread_id=thread_id,
            )
            self._memory_backend.add_message(
                role,
                message,
                thread_id=thread_id,
            )

    def _execute(
        self,
        input: str,
        context: Optional[Dict[str, Any]] = None,
        response_schema: Optional[Type[Any]] = None,
        thread_id: Optional[str] = None,
        **kwargs: Any,
    ) -> AgentResult:
        """Run the agent and return a normalized rich result."""
        self._initialize_memory_for_run()
        execution = self._build_execution_context(
            input, context=context, thread_id=thread_id
        )
        active_schema = response_schema or self.response_schema
        original_schema = self.response_schema
        if active_schema is not self.response_schema:
            self.response_schema = active_schema

        apply_before_run(self._middleware, execution)
        messages = self._build_messages(input, execution)
        execution.emit("run.start", input=input, thread_id=execution.thread_id)

        try:
            raw_result = self._invoke_model(messages, execution, **kwargs)
            output, structured_response, output_messages = (
                self._normalize_agent_output(raw_result)
            )
            usage_details = extract_usage_details(
                raw_result,
                output_messages,
                llm_identifier=self.llm_identifier,
            )
            output = apply_after_run(self._middleware, execution, output)
            structured_response = (
                structured_response
                or self._coerce_structured_output(output, active_schema)
            )
            self._update_history(
                input,
                output,
                thread_id=execution.thread_id,
                usage_details=usage_details,
            )
            self._persist_execution_state(execution, output=output)
            execution.emit("run.end", output=output)
        except ApprovalRequiredError as exc:
            self._persist_execution_state(
                execution, output=exc.request.reason, approval_error=exc
            )
            self._persist_failed_run(
                input,
                exc.request.reason or str(exc),
                role="system",
                thread_id=execution.thread_id,
            )
            execution.emit(
                "run.interrupted",
                tool=exc.request.tool_name,
                reason=exc.request.reason,
            )
            result = AgentResult(
                output=exc.request.reason or str(exc),
                messages=messages,
                structured_response=None,
                state=execution.state,
                events=execution.events,
            )
            self._last_result = result
            return result
        except Exception as exc:
            self._persist_failed_run(
                input,
                str(exc),
                role="system",
                thread_id=execution.thread_id,
            )
            raise AgentError(
                f"Error executing agent '{self.name}': {str(exc)}"
            ) from exc
        finally:
            self.response_schema = original_schema

        result = AgentResult(
            output=output,
            messages=output_messages or messages + [AIMessage(content=output)],
            structured_response=structured_response,
            state=execution.state,
            events=execution.events,
        )
        self._last_result = result
        return result

    def _run(
        self,
        input: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """Execute the agent and return the final text output."""
        return self._execute(input, context=context, **kwargs).output

    def run(
        self,
        input: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Public method to run the agent with error handling."""
        return self._run(input, context=context, **kwargs)

    async def arun(
        self,
        input: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Async wrapper around run()."""
        return await asyncio.to_thread(
            self.run, input, context=context, **kwargs
        )

    def invoke(
        self,
        inputs: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Invoke the agent using a LangChain-style messages payload."""
        raw_messages = inputs.get("messages", [])
        message_content = None

        if raw_messages:
            message_content = getattr(raw_messages[-1], "content", None)

        if message_content is None:
            message_content = inputs.get("input")

        if not isinstance(message_content, str) or not message_content:
            raise AgentError(
                "invoke() requires a non-empty 'input' or final message content."
            )

        result = self._execute(message_content, context=context, **kwargs)
        output_messages = (
            list(raw_messages) if raw_messages else list(result.messages)
        )
        if raw_messages:
            output_messages.append(AIMessage(content=str(result.output)))

        payload = {
            "messages": output_messages,
            "output": result.output,
            "thread_id": result.state.get(
                "thread_id", self._resolve_thread_id()
            ),
            "state": result.state,
        }
        if result.structured_response is not None:
            payload["structured_response"] = result.structured_response
        return payload

    async def ainvoke(
        self,
        inputs: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Async wrapper around invoke()."""
        return await asyncio.to_thread(
            self.invoke, inputs, context=context, **kwargs
        )

    def stream(
        self,
        input: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ):
        """Yield execution events for a run."""
        result = self._execute(input, context=context, **kwargs)
        for event in result.events:
            yield event
        yield result.output

    async def astream(
        self,
        input: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ):
        """Async generator yielding execution events."""
        result = await asyncio.to_thread(
            self._execute, input, context, **kwargs
        )
        for event in result.events:
            yield event
        yield result.output

    def approve_pending_tool(
        self, tool_name: Optional[str] = None, thread_id: Optional[str] = None
    ) -> None:
        """Mark a pending tool as approved for the next execution attempt."""
        active_thread_id = thread_id or self._resolve_thread_id()
        state = self._state_store.load(active_thread_id)
        if (
            tool_name
            and state.paused_tool_name
            and state.paused_tool_name != tool_name
        ):
            raise AgentError(
                f"Thread '{active_thread_id}' is waiting on "
                f"'{state.paused_tool_name}', not '{tool_name}'."
            )
        approvals = state.values.get("approved_tools", {})
        if state.paused_tool_name:
            approvals[state.paused_tool_name] = True
        state.values["approved_tools"] = approvals
        state.status = "approved"
        self._state_store.save(state)

    def get_thread_state(
        self, thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Return durable state for a thread."""
        active_thread_id = thread_id or self._resolve_thread_id()
        return self._state_store.load(active_thread_id).to_dict()

    def remember(
        self,
        key: str,
        value: str,
        *,
        scope: str = "user",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Persist a long-term memory fact."""
        conversation = (
            getattr(self._memory_backend, "conversation", None)
            if self._memory_backend
            else None
        )
        user = (
            getattr(self._memory_backend, "user", None)
            if self._memory_backend
            else None
        )
        return memory_store.put(
            key,
            value,
            scope=scope,
            agent_name=self.name,
            user=user,
            conversation=conversation,
            metadata=metadata,
        )

    def recall(
        self,
        key: str,
        *,
        scope: str = "user",
    ) -> Optional[str]:
        """Fetch a long-term memory fact."""
        conversation = (
            getattr(self._memory_backend, "conversation", None)
            if self._memory_backend
            else None
        )
        user = (
            getattr(self._memory_backend, "user", None)
            if self._memory_backend
            else None
        )
        return memory_store.get(
            key, scope=scope, user=user, conversation=conversation
        )

    def list_memories(
        self, *, scope: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List long-term memory facts for the current agent/user."""
        conversation = (
            getattr(self._memory_backend, "conversation", None)
            if self._memory_backend
            else None
        )
        user = (
            getattr(self._memory_backend, "user", None)
            if self._memory_backend
            else None
        )
        return memory_store.list(
            scope=scope,
            user=user,
            conversation=conversation,
            agent_name=self.name,
            limit=limit,
        )

    def clear_memory(self) -> None:
        """Clear the agent's conversation history and runtime state."""
        self._message_history.clear()
        if self._memory_backend:
            self._memory_backend.clear()
        self._state_store.clear(self._resolve_thread_id())

    def get_history(self) -> List[BaseMessage]:
        """Get the conversation history."""
        return self._message_history.copy()

    def get_conversation_info(self) -> Optional[Dict[str, Any]]:
        """Get conversation information for the active backend."""
        if self._memory_backend:
            return self._memory_backend.get_conversation_info()
        return None

    def get_conversation_id(self) -> Optional[str]:
        """Get the current conversation ID."""
        if self._memory_backend:
            return self._memory_backend.conversation_id
        return None

    @classmethod
    def create(
        cls,
        name: str,
        tools: Optional[List[Union[str, Tool, Callable, Any]]] = None,
        memory: bool = True,
        memory_backend: str = "memory",
        conversation_id: Optional[str] = None,
        conversation_name: Optional[str] = None,
        user: Optional[Any] = None,
        system_prompt: Optional[str] = None,
        auto_load_tools: bool = False,
        llm_provider: Optional[str] = None,
        middleware: Optional[List[AgentMiddleware]] = None,
        response_schema: Optional[Type[Any]] = None,
        mcp_servers: Optional[Dict[str, Dict[str, Any]]] = None,
        langchain_middleware: Optional[Dict[str, Any]] = None,
        checkpointer: Optional[Any] = None,
        thread_id: Optional[str] = None,
        **kwargs: Any,
    ) -> "Agent":
        """Factory method to create an agent."""
        """
        Factory method to create an agent.

        Args:
            name: Agent name (you choose the name)
            tools: List of tools
            memory: Enable conversation memory
            memory_backend: Backend type ("memory" or "database")
            conversation_id: Existing conversation ID to resume
            conversation_name: Name for new conversation
            user: User to associate with conversation
            system_prompt: System prompt
            auto_load_tools: If True, load all registered tools from ToolRegistry
            llm_provider: Optional provider override (e.g., "google", "openai")
            **kwargs: Additional configuration

        Returns:
            An Agent instance

        Example:
            # In-memory (default)
            agent = Agent.create(
                name="assistant",
                auto_load_tools=True,
                memory=True,
            )

            # Database-backed persistent memory
            agent = Agent.create(
                name="assistant",
                memory_backend="database",
                user=request.user,
            )

            # Resume existing conversation
            agent = Agent.create(
                name="assistant",
                memory_backend="database",
                conversation_id="existing-uuid",
            )

            # Override provider
            agent = Agent.create(
                name="assistant",
                llm_provider="openai",
            )
        """
        from django.conf import settings

        # Get LLM from settings or provider override
        djgent_settings = getattr(settings, "DJGENT", {})
        llm_string = llm_provider or djgent_settings.get(
            "DEFAULT_LLM", "google:gemini-2.5-flash"
        )
        llm_instance = get_llm(llm_string)

        processed_tools = list(tools) if tools else []

        if auto_load_tools:
            for tool_name in ToolRegistry.list_tools():
                if tool_name not in processed_tools:
                    processed_tools.append(tool_name)

        if mcp_servers:
            processed_tools.extend(load_mcp_tools(mcp_servers))

        return cls(
            name=name,
            llm=llm_instance,
            tools=processed_tools,
            memory=memory,
            memory_backend=memory_backend,
            conversation_id=conversation_id,
            conversation_name=conversation_name,
            user=user,
            system_prompt=system_prompt,
            middleware=middleware,
            response_schema=response_schema,
            thread_id=thread_id,
            langchain_middleware=langchain_middleware,
            checkpointer=checkpointer,
            **kwargs,
        )

    @classmethod
    def create_multi(
        cls,
        name: str,
        agents: Optional[List[Union[Dict[str, Any], "Agent"]]] = None,
        main_agent_config: Optional[Dict[str, Any]] = None,
        memory: bool = True,
        memory_backend: str = "memory",
        verbose: bool = False,
        **kwargs: Any,
    ) -> "MultiAgent":
        """
        Factory method to create a multi-agent system using the Subagents pattern.

        This method creates specialized agents and coordinates them through a main
        coordinator agent. Each subagent handles specific tasks based on their
        configuration.

        Args:
            name: Team name
            agents: List of agent configurations or Agent instances. Each item can be:
                - Agent instance: Pre-created Agent object
                - Dict with configuration:
                    - name: str (agent name)
                    - role: str (specialization/role description for routing)
                    - tools: Optional[List] (tool names or instances)
                    - system_prompt: Optional[str] (specialized system prompt)
                    - llm_provider: Optional[str] (override provider)
                    - memory: bool (enable memory for this subagent, default True)
            main_agent_config: Configuration for the main coordinator agent:
                - system_prompt: Optional[str] (routing instructions)
                - tools: Optional[List] (additional tools for main agent)
                - llm_provider: Optional[str]
            memory: Enable conversation memory for main agent
            memory_backend: Backend type ("memory" or "database")
            verbose: Enable detailed logging
            **kwargs: Additional MultiAgent settings

        Returns:
            MultiAgent instance

        Raises:
            AgentError: If no agents are provided

        Example:
            # Using Agent objects directly
            tech_agent = Agent.create(
                name="tech-agent",
                system_prompt="You handle technical questions.",
                tools=["django_model"],
            )
            billing_agent = Agent.create(
                name="billing-agent",
                system_prompt="You handle billing questions.",
                tools=["django_model"],
            )

            team = Agent.create_multi(
                name="customer-support",
                agents=[tech_agent, billing_agent],  # Pass Agent objects
            )

            # Using configuration dicts
            team = Agent.create_multi(
                name="customer-support",
                agents=[
                    {
                        "name": "tech-agent",
                        "role": "Technical support for Django and Python",
                        "system_prompt": "You handle technical questions.",
                        "tools": ["django_model"],
                    },
                    {
                        "name": "billing-agent",
                        "role": "Billing and payment questions",
                        "system_prompt": "You handle billing questions.",
                        "tools": ["django_model"],
                    },
                ],
            )

            # Mixed: Agent objects and dicts
            team = Agent.create_multi(
                name="support-team",
                agents=[
                    tech_agent,  # Agent object
                    {
                        "name": "billing-agent",
                        "role": "Billing support",
                        "system_prompt": "You handle billing.",
                        "tools": ["django_model"],
                    },
                ],
            )

            response = team.run("I was charged twice")
        """
        from djgent.agents.multi_agent import MultiAgent

        if not agents:
            raise AgentError("At least one agent must be provided")

        # Process agents - support both Agent objects and dict configs
        subagents = []
        for agent_item in agents:
            if isinstance(agent_item, Agent):
                # Agent object provided directly
                subagent = agent_item
                role = f"Specialist: {subagent.name}"
                if subagent.system_prompt:
                    role = subagent.system_prompt.strip().split("\n")[0]
                subagents.append((subagent, role))
            elif isinstance(agent_item, dict):
                # Dict configuration provided
                agent_config = agent_item
                agent_name = agent_config.get("name")
                if not agent_name:
                    raise AgentError(
                        "Each agent configuration must include a 'name' field"
                    )

                role = agent_config.get("role", f"Specialist: {agent_name}")
                agent_memory = agent_config.get("memory", memory)

                # Extract agent-specific config
                agent_kwargs = {
                    "name": agent_name,
                    "tools": agent_config.get("tools"),
                    "system_prompt": agent_config.get("system_prompt"),
                    "llm_provider": agent_config.get("llm_provider"),
                    "memory": agent_memory,
                    "memory_backend": memory_backend,
                }

                # Create the agent
                subagent = cls.create(
                    **{k: v for k, v in agent_kwargs.items() if v is not None}
                )
                subagents.append((subagent, role))
            else:
                raise AgentError(
                    f"Agent must be an Agent instance or dict configuration, "
                    f"got {type(agent_item)}"
                )

        # Create MultiAgent instance
        return MultiAgent(
            name=name,
            subagents=subagents,
            main_agent_config=main_agent_config,
            memory=memory,
            memory_backend=memory_backend,
            verbose=verbose,
            **kwargs,
        )

    def __call__(self, input: str, **kwargs: Any) -> Any:
        """Allow the agent to be called directly."""
        return self.run(input, **kwargs)
