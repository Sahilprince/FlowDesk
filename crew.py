from crewai import Agent, Task, Crew, Process
from crewai_tools import tool
from langchain_openai import ChatOpenAI
import os

# Connect CrewAI to vLLM (OpenAI-compatible)
llm = ChatOpenAI(
    model="llama3.1:8b",
    base_url="http://localhost:11434/v1",
    api_key="ollama",
    temperature=0.1,
)

# ── TOOLS ────────────────────────────────────────────────────────────────────

@tool("gmail_read")
def gmail_read(query: str) -> str:
    """Read emails from Gmail matching a query."""
    # TODO: wire Gmail MCP
    return f"[Gmail] Fetched emails for: {query}"

@tool("gmail_send")
def gmail_send(to: str, subject: str, body: str) -> str:
    """Draft and queue a Gmail email for approval."""
    return f"[PENDING_APPROVAL] Send to={to} subject={subject} body={body}"

@tool("calendar_read")
def calendar_read(date_range: str) -> str:
    """Read calendar events for a date range."""
    return f"[Calendar] Events for: {date_range}"

@tool("calendar_create")
def calendar_create(title: str, datetime: str, attendees: str) -> str:
    """Queue a calendar event creation for approval."""
    return f"[PENDING_APPROVAL] Event={title} at={datetime} attendees={attendees}"

@tool("save_workflow")
def save_workflow(name: str, trigger: str, condition: str, action: str) -> str:
    """Save a reusable workflow to the database."""
    return f"[Workflow Saved] {name}: IF {trigger} AND {condition} THEN {action}"

# ── AGENTS ───────────────────────────────────────────────────────────────────

intent_router = Agent(
    role="Intent Router",
    goal="Classify user input as: one_time_task | create_workflow | status_check",
    backstory="You parse natural language requests and route them precisely.",
    llm=llm,
    verbose=False,
    allow_delegation=True,
)

task_agent = Agent(
    role="Task Executor",
    goal="Execute one-time tasks using Gmail and Calendar tools. Always stage for approval first.",
    backstory="You are a personal assistant that executes tasks carefully and never acts without queuing for approval.",
    tools=[gmail_read, gmail_send, calendar_read, calendar_create],
    llm=llm,
    verbose=True,
)

workflow_agent = Agent(
    role="Workflow Builder",
    goal="Build reusable trigger→condition→action workflows from natural language and save them.",
    backstory="You convert user intent into structured workflows that run automatically.",
    tools=[save_workflow],
    llm=llm,
    verbose=True,
)

# ── CREW FACTORY ─────────────────────────────────────────────────────────────

def run_flowdesk(user_input: str) -> dict:
    """Main entry point - routes and executes user request."""

    route_task = Task(
        description=f"""
        Classify this user request:
        "{user_input}"
        
        Return ONLY one of: one_time_task | create_workflow | status_check
        Then briefly explain what needs to be done.
        """,
        agent=intent_router,
        expected_output="Classification and action plan",
    )

    execute_task = Task(
        description=f"""
        Based on the routing decision, handle this request:
        "{user_input}"
        
        If one_time_task: Use tools to execute. Stage destructive actions for approval.
        If create_workflow: Build and save a workflow using save_workflow tool.
        If status_check: Read relevant data and summarize.
        
        Return a structured response with: action_taken, pending_approvals[], summary
        """,
        agent=task_agent,  # task_agent delegates to workflow_agent if needed
        expected_output="Structured result with action_taken and pending_approvals",
        context=[route_task],
    )

    crew = Crew(
        agents=[intent_router, task_agent, workflow_agent],
        tasks=[route_task, execute_task],
        process=Process.sequential,
        verbose=False,
    )

    result = crew.kickoff()
    return {"result": str(result), "input": user_input}
