"""Multi-agent coordination using the Subagents pattern."""

from typing import Any, Dict, List, Optional, Tuple, Union

from djgent.agents.base import Agent
from djgent.exceptions import AgentError
from djgent.tools.base import Tool


class SubAgentTool(Tool):
    """
    Wraps a subagent as a tool that can be invoked by the main agent.

    This provides context isolation—each subagent only sees the information
    passed to it by the main agent.
    """

    def __init__(self, agent: Agent, role: str):
        """
        Initialize subagent tool wrapper.

        Args:
            agent: The Agent instance to wrap
            role: Role description for this subagent
        """
        self.agent = agent
        self.role = role
        self.name = f"{agent.name}_subagent"
        self.description = f"Invoke {agent.name} for: {role}"
        super().__init__()

    def _run(self, query: str) -> str:
        """
        Execute the subagent with the given query.

        Args:
            query: The query to pass to the subagent

        Returns:
            The subagent's response
        """
        return self.agent.run(query)


class MultiAgent:
    """
    Multi-agent coordinator using the Subagents pattern.

    The main agent coordinates specialized subagents, invoking them as tools
    based on the user's request.

    This pattern provides:
    - Context isolation: Each subagent only sees information passed to it
    - Specialized expertise: Each subagent can have its own tools and prompts
    - Parallelization: Multiple subagents can be invoked concurrently
    - Distributed development: Subagents can be developed/maintained independently

    Example:
        # Create specialized agents
        tech_agent = Agent.create(
            name="tech-agent",
            system_prompt="You handle technical questions about Django and Python.",
            tools=["django_model"],
        )

        billing_agent = Agent.create(
            name="billing-agent",
            system_prompt="You handle billing and payment questions.",
            tools=["django_model"],
        )

        # Create multi-agent team
        team = MultiAgent(
            name="customer-support",
            subagents=[tech_agent, billing_agent],
        )

        response = team.run("I was charged twice for my subscription")
        print(response)  # billing-agent handles this
    """

    # Default system prompt for the main coordinator agent
    DEFAULT_MAIN_AGENT_PROMPT = """
You are the coordinator of a multi-agent team. Your role is to:

1. Understand the user's request
2. Determine which specialist is best suited to handle it
3. Invoke the appropriate specialist with a clear query
4. Review the specialist's response
5. Return a comprehensive answer to the user

Available specialists:
{subagent_descriptions}

Think step-by-step:
- First, identify which specialist has the right expertise
- Then, invoke them with a clear, specific query
- Finally, synthesize their response for the user

If you're unsure which specialist to use, or if the request requires multiple
specialists, invoke them one at a time and combine their responses.

Important:
- Always invoke specialists using their exact tool names (e.g., "tech_agent_subagent")
- Provide clear, specific queries to specialists
- If a specialist cannot help, try another specialist or respond with what you know
"""

    def __init__(
        self,
        name: str,
        subagents: Optional[List[Union[Agent, Tuple[Agent, str]]]] = None,
        main_agent: Optional[Agent] = None,
        main_agent_config: Optional[Dict[str, Any]] = None,
        memory: bool = True,
        memory_backend: str = "memory",
        verbose: bool = False,
    ):
        """
        Initialize multi-agent coordinator.

        Args:
            name: Team name
            subagents: List of Agent instances or (Agent, role_description) tuples
            main_agent: Optional custom main/coordination agent
            main_agent_config: Config for auto-created main agent:
                - system_prompt: str
                - tools: List
                - llm_provider: Optional[str]
            memory: Enable conversation memory for main agent
            memory_backend: Backend type ("memory" or "database")
            verbose: Enable detailed logging

        Example:
            # Basic usage with agent objects
            team = MultiAgent(
                name="support-team",
                subagents=[tech_agent, billing_agent],
            )

            # With role descriptions
            team = MultiAgent(
                name="support-team",
                subagents=[
                    (tech_agent, "Technical support for Django and Python"),
                    (billing_agent, "Billing and payment questions"),
                ],
            )

            # With custom main agent
            team = MultiAgent(
                name="support-team",
                subagents=[tech_agent, billing_agent],
                main_agent=coordinator_agent,
            )
        """
        self.name = name
        self.main_agent = main_agent
        self.subagents: Dict[str, Agent] = {}  # name -> Agent
        self.subagent_roles: Dict[str, str] = {}  # name -> role description
        self.subagent_tools: Dict[str, SubAgentTool] = {}  # name -> tool
        self.verbose = verbose
        self.memory = memory
        self.memory_backend = memory_backend

        # Process subagents
        if subagents:
            for item in subagents:
                if isinstance(item, tuple):
                    agent, role = item
                    self.add_subagent(agent, role)
                else:
                    self.add_subagent(item)

        # Build main agent if not provided
        if not self.main_agent:
            self._build_main_agent(main_agent_config or {})

    def add_subagent(
        self,
        agent: Agent,
        role: Optional[str] = None,
    ) -> None:
        """
        Add a subagent to the team.

        Args:
            agent: Agent instance to add
            role: Optional role description (uses agent's system_prompt if not provided)

        Example:
            tech_agent = Agent.create(name="tech-agent", tools=["django_model"])
            team.add_subagent(tech_agent, role="Technical support specialist")
        """
        agent_name = agent.name
        self.subagents[agent_name] = agent

        # Use provided role or extract from agent's system_prompt
        if role:
            self.subagent_roles[agent_name] = role
        elif agent.system_prompt:
            # Use first line of system_prompt as role
            self.subagent_roles[agent_name] = agent.system_prompt.strip().split("\n")[0]
        else:
            self.subagent_roles[agent_name] = f"Specialist agent: {agent_name}"

        # Create tool wrapper
        tool = SubAgentTool(agent, self.subagent_roles[agent_name])
        self.subagent_tools[agent_name] = tool

        if self.verbose:
            print(
                f"[MultiAgent:{self.name}] Added subagent: "
                f"{agent_name} - {self.subagent_roles[agent_name]}"
            )

    def remove_subagent(self, agent_name: str) -> bool:
        """
        Remove a subagent from the team.

        Args:
            agent_name: Name of the agent to remove

        Returns:
            True if removed, False if agent not found
        """
        if agent_name in self.subagents:
            del self.subagents[agent_name]
            del self.subagent_roles[agent_name]
            del self.subagent_tools[agent_name]

            if self.verbose:
                print(f"[MultiAgent:{self.name}] Removed subagent: {agent_name}")
            return True
        return False

    def get_subagent(self, name: str) -> Optional[Agent]:
        """
        Get a subagent by name.

        Args:
            name: Name of the subagent

        Returns:
            Agent instance or None if not found
        """
        return self.subagents.get(name)

    def list_subagents(self) -> List[Dict[str, str]]:
        """
        List all subagents with their names and roles.

        Returns:
            List of dicts with 'name' and 'role' keys

        Example:
            for subagent in team.list_subagents():
                print(f"{subagent['name']}: {subagent['role']}")
        """
        return [{"name": name, "role": role} for name, role in self.subagent_roles.items()]

    def _build_main_agent(self, config: Dict[str, Any]) -> None:
        """
        Build the main coordinator agent with subagent tools.

        Args:
            config: Configuration for the main agent
        """
        # Build subagent descriptions for the prompt
        subagent_descriptions = self._format_subagent_descriptions()

        # Create system prompt
        system_prompt = config.get(
            "system_prompt",
            self.DEFAULT_MAIN_AGENT_PROMPT.format(subagent_descriptions=subagent_descriptions),
        )

        # Collect all subagent tools
        tools = list(self.subagent_tools.values())

        # Add any additional tools from config
        additional_tools = config.get("tools", [])
        if additional_tools:
            tools.extend(additional_tools)

        # Create main agent
        llm_provider = config.get("llm_provider")

        self.main_agent = Agent.create(
            name=f"{self.name}-coordinator",
            tools=tools,
            memory=self.memory,
            memory_backend=self.memory_backend,
            system_prompt=system_prompt,
            llm_provider=llm_provider,
        )

        if self.verbose:
            print(
                f"[MultiAgent:{self.name}] Created main coordinator agent with {len(tools)} tools"
            )

    def _format_subagent_descriptions(self) -> str:
        """
        Format subagent descriptions for the main agent prompt.

        Returns:
            Formatted string with subagent names and roles
        """
        lines = []
        for name, role in self.subagent_roles.items():
            tool_name = f"{name}_subagent"
            lines.append(f"- {tool_name}: {role}")
        return "\n".join(lines) if lines else "No specialists available."

    def run(self, input: str, **kwargs: Any) -> str:
        """
        Execute the multi-agent system with the given input.

        The main agent coordinates the request, invoking subagents as needed.

        Args:
            input: The user's request or question
            **kwargs: Additional arguments passed to the main agent

        Returns:
            The coordinated response

        Example:
            response = team.run("I was charged twice for my subscription")
            print(response)
        """
        if not self.main_agent:
            raise AgentError(f"MultiAgent '{self.name}' has no main agent configured")

        if self.verbose:
            print(f"[MultiAgent:{self.name}] Processing request: {input[:100]}...")

        try:
            result = self.main_agent.run(input, **kwargs)

            if self.verbose:
                print(f"[MultiAgent:{self.name}] Response: {result[:100]}...")

            return result
        except Exception as e:
            raise AgentError(f"Error in MultiAgent '{self.name}': {str(e)}") from e

    def run_parallel(
        self,
        input: str,
        subagent_names: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """
        Run the input through multiple subagents in parallel.

        Args:
            input: The user's request or question
            subagent_names: Optional list of subagent names to invoke.
                           If None, invokes all subagents.

        Returns:
            Dict mapping subagent names to their responses

        Example:
            responses = team.run_parallel("What do you know about Django?")
            for name, response in responses.items():
                print(f"{name}: {response}")
        """
        import concurrent.futures

        # Determine which subagents to invoke
        if subagent_names:
            agents_to_invoke = [
                (name, self.subagents[name]) for name in subagent_names if name in self.subagents
            ]
        else:
            agents_to_invoke = list(self.subagents.items())

        if not agents_to_invoke:
            return {}

        # Invoke subagents in parallel
        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(agents_to_invoke)) as executor:
            # Submit all tasks
            future_to_name = {
                executor.submit(agent.run, input): name for name, agent in agents_to_invoke
            }

            # Collect results
            for future in concurrent.futures.as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    results[name] = future.result()
                except Exception as e:
                    results[name] = f"Error: {str(e)}"

        return results

    def get_conversation_id(self) -> Optional[str]:
        """
        Get the current conversation ID from the main agent.

        Returns:
            Conversation ID string, or None if using in-memory backend
        """
        if self.main_agent:
            return self.main_agent.get_conversation_id()
        return None

    def get_conversation_info(self) -> Optional[Dict[str, Any]]:
        """
        Get conversation information from the main agent.

        Returns:
            Dictionary with conversation metadata, or None if using in-memory backend
        """
        if self.main_agent:
            return self.main_agent.get_conversation_info()
        return None

    def clear_memory(self) -> None:
        """Clear conversation history for the main agent and all subagents."""
        if self.main_agent:
            self.main_agent.clear_memory()

        for agent in self.subagents.values():
            agent.clear_memory()

        if self.verbose:
            print(f"[MultiAgent:{self.name}] Cleared conversation memory")

    def __call__(self, input: str, **kwargs: Any) -> str:
        """Allow the multi-agent to be called directly."""
        return self.run(input, **kwargs)
