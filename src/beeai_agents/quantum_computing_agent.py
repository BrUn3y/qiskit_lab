"""
Quantum Computing Agent - Specialist in Quantum Circuit Execution

This agent is a specialist in:
- Execute QASM/Qiskit code on IBM quantum computers
- Manage execution on simulators and real hardware
- Provide detailed information on executed jobs
- Automatic circuit transpilation

Model: configurable via COMPUTING_MODEL (Ollama/Watsonx)
Port: 8003
Type: AgentStack Server with A2A (ReActAgent with IBMQuantumTool)
"""

import os
import re
import tempfile
from datetime import datetime
from typing import Annotated
from collections.abc import AsyncGenerator
from pathlib import Path

from a2a.types import AgentSkill, Message, TextPart
from a2a.utils.message import get_message_text
from agentstack_sdk.server import Server
from agentstack_sdk.server.context import RunContext
from agentstack_sdk.server.store.platform_context_store import PlatformContextStore
from agentstack_sdk.a2a.types import AgentArtifact, AgentMessage
from agentstack_sdk.a2a.extensions import AgentDetail, AgentDetailTool
from agentstack_sdk.a2a.extensions import TrajectoryExtensionServer, TrajectoryExtensionSpec
from agentstack_sdk.a2a.extensions.ui.canvas import CanvasExtensionServer, CanvasExtensionSpec
from agentstack_sdk.platform.file import File

from beeai_framework.agents.react import ReActAgent
from beeai_framework.memory import UnconstrainedMemory

from .model_config import create_chat_model, explain_error, model_name, run_agent_with_retries
from .execution_visualization import RESULT_CANVAS_MARKER

# Import the execution tool
from .tools import IBMQuantumTool

# Instructions for the Computing Agent (without custom template to avoid parsing errors)
COMPUTING_INSTRUCTIONS = """You are the Quantum Computing Agent. You execute quantum circuits on IBM Quantum.

⚠️ CRITICAL RULE: Your response MUST ALWAYS include the Job ID prominently.

STEPS:
1. Extract QASM code from user request
2. Identify backend (if specified, otherwise use ibm_kyiv)
3. Execute with ibm_quantum_operator
4. In your final response, ALWAYS include:
   - ⚠️ **Job ID: [the_real_job_id]** (in bold and with warning emoji)
   - Backend used
   - Shots
   - Results (if available)

RESPONSE FORMAT:
```
🚀 Circuit executed successfully

⚠️ **Job ID: abc123xyz456** ← THIS IS MANDATORY

Backend: ibm_torino
Shots: 1024
Status: DONE

[Results if available]
```

The Job ID is CRITICAL because quantum computers take time to respond and the user needs the ID to query results later.
"""

# Agent details for AgentStack
COMPUTING_AGENT_DETAIL = AgentDetail(
    user_greeting="⚡ Hello! I'm the Quantum Computing Agent. I execute quantum circuits on IBM Quantum simulators and real hardware, managing transpilation and providing Job IDs for tracking.",
    version="1.0.0",
    framework="BeeAI + A2A (Watsonx/Ollama)",
    author={"name": "Edgar Bruney"},
    tools=[
        AgentDetailTool(
            name="IBM Quantum Executor",
            description="Executes QASM/Qiskit code on IBM quantum computers (simulators or real hardware) with automatic transpilation."
        )
    ],
)

# Skills exposed by the agent
COMPUTING_AGENT_SKILLS = [
    AgentSkill(
        id="quantum-circuit-execution",
        name="Quantum Circuit Execution",
        description="Executes quantum circuits on IBM Quantum simulators or real hardware with automatic transpilation management.",
        tags=["Quantum Computing", "IBM Quantum", "Circuit Execution", "QASM", "Qiskit"],
        examples=[
            "Execute this QASM code on ibm_torino",
            "Execute this circuit on ibm_brisbane",
            "Execute the circuit on the ibm_kyiv simulator",
            "Run this QASM code on real quantum hardware",
            "Execute this circuit with 2048 shots on ibm_osaka"
        ]
    )
]

# Create the Agent Stack server.
server = Server()


_QASM_FENCE_PATTERN = re.compile(r"```(?:open)?qasm\s*(OPENQASM\s+[\s\S]*?)```", re.IGNORECASE)
_QASM_PATTERN = re.compile(r"OPENQASM\s+(?:2\.0|3\.0)\s*;[\s\S]*", re.IGNORECASE)
_BACKEND_PATTERN = re.compile(r"\b(?:ibm|ibmq)_[a-z0-9_]+\b", re.IGNORECASE)
_SHOTS_PATTERN = re.compile(r"\b(\d+)\s*(?:shots?|disparos?)\b", re.IGNORECASE)
_SIMULATOR_PATTERN = re.compile(
    r"\b(local\s+simulator|simulat(?:e|ed|ion|or)|simulador|simulaci[oó]n|simular|simulad[oa])\b",
    re.IGNORECASE,
)
_SIMULATOR_NEGATION_PATTERN = re.compile(
    r"\b(?:no|not|without|sin)\s+(?:a\s+|the\s+|el\s+|un\s+)?"
    r"(?:simulator|simulation|simulador|simulaci[oó]n)\b",
    re.IGNORECASE,
)
_EXECUTION_TAG_PATTERNS = (
    (re.compile(r"\b(qaoa|max[- ]?cut|maxcut)\b", re.IGNORECASE), "qaoa-maxcut"),
    (re.compile(r"\b(bell(?:\s+state)?|estado\s+de\s+bell)\b", re.IGNORECASE), "bell-state"),
    (re.compile(r"\bgrover(?:'s)?\b", re.IGNORECASE), "grover-search"),
    (re.compile(r"\bdeutsch[- ]?jozsa\b", re.IGNORECASE), "deutsch-jozsa"),
    (re.compile(r"\b(cx|cnot|controlled[- ]?not)\b", re.IGNORECASE), "cx-gate"),
    (re.compile(r"\b(superposition|superposici[oó]n)\b", re.IGNORECASE), "superposition"),
    (re.compile(r"\b(teleportation|teleportaci[oó]n)\b", re.IGNORECASE), "teleportation"),
    (re.compile(r"\b(qft|quantum fourier|fourier cu[aá]ntica)\b", re.IGNORECASE), "qft"),
)


def _extract_qasm(request: str) -> str | None:
    """Extract the QASM payload supplied by the orchestrator or user."""
    fenced_match = _QASM_FENCE_PATTERN.search(request)
    if fenced_match:
        return fenced_match.group(1).strip()

    qasm_match = _QASM_PATTERN.search(request)
    if not qasm_match:
        return None

    qasm = re.split(r"\n\s*---\s*\n", qasm_match.group(0), maxsplit=1)[0]
    return qasm.strip()


def _execution_parameters(request: str) -> dict[str, object]:
    """Parse execution parameters without requiring an LLM tool call."""
    # The Lab Agent appends execution policy and QASM after this delimiter.
    # Only the original user request may select simulator versus real hardware.
    request_scope = request.split("\n\nExecute exactly once.", 1)[0]
    backend_match = _BACKEND_PATTERN.search(request_scope)
    shots_match = _SHOTS_PATTERN.search(request_scope)
    backend_name = backend_match.group(0) if backend_match else ""
    simulator_requested = bool(_SIMULATOR_PATTERN.search(request_scope)) and not bool(
        _SIMULATOR_NEGATION_PATTERN.search(request_scope)
    )
    named_simulator = bool(backend_name and "simulator" in backend_name.lower())
    execution_tag = next(
        (tag for pattern, tag in _EXECUTION_TAG_PATTERNS if pattern.search(request_scope)),
        "quantum-circuit",
    )
    return {
        "backend_name": backend_name,
        # Every execution creates a fresh QPU job by default. A local simulator
        # is used only when the original user request explicitly asks for one.
        "use_real_device": not (simulator_requested or named_simulator),
        "shots": int(shots_match.group(1)) if shots_match else 1024,
        "wait_for_results": False,
        "max_wait_time": 300,
        "job_tags": ["quantum-lab", execution_tag],
    }

async def _create_execution_canvas(text: str, qasm_code: str) -> tuple[str, AgentArtifact | None]:
    """Upload a completed execution dashboard and expose it through Canvas."""
    match = RESULT_CANVAS_MARKER.search(text)
    clean_text = RESULT_CANVAS_MARKER.sub("", text).rstrip()
    if not match:
        return clean_text, None

    dashboard_path = Path(match.group(1).strip()).resolve()
    allowed_directory = (Path(tempfile.gettempdir()) / "quantum_lab_pngs").resolve()
    if dashboard_path.parent != allowed_directory or not dashboard_path.is_file():
        return clean_text + "\n\n⚠️ The execution dashboard could not be loaded safely.", None

    backend_match = re.search(r"\*\*Backend:\*\*\s*([^\n]+)", clean_text)
    job_match = re.search(r"\*\*Job ID:\*\*\s*`?([^`\n]+)", clean_text)
    backend_name = backend_match.group(1).strip() if backend_match else "quantum backend"
    job_id = job_match.group(1).strip() if job_match else "local execution"
    try:
        uploaded = await File.create(
            filename=f"{job_id}_execution_results.png",
            content=dashboard_path.read_bytes(),
            content_type="image/png",
        )
        image_markdown = f"![Quantum execution results](agentstack://{uploaded.id})"
        queried_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        artifact = AgentArtifact(
            name=f"{backend_name} execution results",
            description=f"Measurement outcomes and circuit for job {job_id}.",
            metadata={"backend": backend_name, "job_id": job_id, "content_type": "text/markdown"},
            parts=[TextPart(text=f"{image_markdown}\n\nConsulted locally: {queried_at}\n\n```qasm\n{qasm_code}\n```")],
        )
        clean_text += f"\n\n## 📊 Visual execution results\n\n{image_markdown}\n\nThe complete dashboard is available in Canvas."
        return clean_text, artifact
    except Exception as error:
        return clean_text + f"\n\n⚠️ Canvas upload failed: {explain_error(error)}", None
    finally:
        dashboard_path.unlink(missing_ok=True)


def create_computing_agent():
    """Create the Quantum Computing Agent with its configured chat model."""
    llm = create_chat_model("COMPUTING")
    
    # Create the agent using ReActAgent
    return ReActAgent(
        llm=llm,
        tools=[IBMQuantumTool()],
        memory=UnconstrainedMemory(),
    )

@server.agent(
    name="Quantum Computing Agent",
    detail=COMPUTING_AGENT_DETAIL,
    skills=COMPUTING_AGENT_SKILLS,
    default_output_modes=["text/plain", "image/png"],
)
async def quantum_computing_agent(
    input: Message,
    context: RunContext,
    trajectory: Annotated[TrajectoryExtensionServer, TrajectoryExtensionSpec()],
    _canvas: Annotated[CanvasExtensionServer, CanvasExtensionSpec()],
):
    """
    Main handler for the Quantum Computing Agent.
    
    This agent executes quantum circuits on IBM Quantum.
    """
    user_query = get_message_text(input)
    print("=" * 80)
    print(f"⚡ [Computing Agent] Received query: '{user_query[:100]}...'")
    print("=" * 80)
    
    # Step 1: Request analysis
    yield trajectory.trajectory_metadata(
        title="🔍 Analyzing execution request",
        content=f"Processing user query:\n```\n{user_query[:200]}{'...' if len(user_query) > 200 else ''}\n```"
    )

    qasm_code = _extract_qasm(user_query)
    if qasm_code:
        parameters = _execution_parameters(user_query)
        yield trajectory.trajectory_metadata(
            title="⚙️ Executing validated QASM",
            content=(
                "Using deterministic execution parameters:\n"
                f"- Backend: {parameters['backend_name'] or 'least busy/default'}\n"
                f"- Real hardware: {parameters['use_real_device']}\n"
                f"- Shots: {parameters['shots']}\n"
                f"- Tags: {', '.join(parameters['job_tags'])}"
            ),
        )
        try:
            tool_output = await IBMQuantumTool().run({"qasm_code": qasm_code, **parameters})
            response, artifact = await _create_execution_canvas(tool_output.get_text_content(), qasm_code)
            if artifact:
                yield artifact
                try:
                    await context.store(artifact)
                except Exception as store_error:
                    print(f"⚠️ [Canvas] Could not store execution artifact: {explain_error(store_error)}")
            succeeded = "**Job ID:**" in response
            yield trajectory.trajectory_metadata(
                title="✅ Job submitted" if succeeded else "❌ Execution failed",
                content=(
                    "IBM Quantum returned a Job ID." if succeeded
                    else "IBM Quantum rejected the execution request; see the response for details."
                ),
            )
            yield AgentMessage(text=response)
        except Exception as e:
            yield trajectory.trajectory_metadata(
                title="❌ Execution failed",
                content=f"**Type:** {type(e).__name__}\n**Message:** {explain_error(e)}",
            )
            yield AgentMessage(text=f"❌ Error in Computing Agent: {explain_error(e)}")
        return
    
    # Create the agent with instructions
    agent = create_computing_agent()
    
    # Step 2: Agent preparation
    yield trajectory.trajectory_metadata(
        title="🤖 Preparing execution agent",
        content=f"**Configuration:**\n- Model: {model_name('COMPUTING')}\n- Tool: IBM Quantum Executor\n- Memory: Unconstrained"
    )
    
    # Build the prompt with system instructions
    full_prompt = f"{COMPUTING_INSTRUCTIONS}\n\n---\n\nUSER REQUEST:\n{user_query}"
    
    # Step 3: Circuit execution
    yield trajectory.trajectory_metadata(
        title="⚙️ Executing quantum circuit",
        content="The agent is executing the circuit on IBM Quantum..."
    )
    
    # Execute the agent
    try:
        run_context = await run_agent_with_retries(agent, full_prompt)
        
        # Update trajectory with progress
        yield trajectory.trajectory_metadata(
            title="✅ Circuit executed",
            content="- [x] QASM code extracted\n- [x] Circuit transpiled\n- [x] Job submitted to IBM Quantum"
        )
        
        # Extract the response.
        response = ""
        if hasattr(run_context, 'output') and run_context.output:
            output = run_context.output
            if isinstance(output, list) and output:
                last_msg = output[-1]
                if hasattr(last_msg, 'text'):
                    response = str(last_msg.text)
                elif hasattr(last_msg, 'content'):
                    response = str(last_msg.content)
                else:
                    response = str(last_msg)
            else:
                response = str(output)
        else:
            response = str(run_context)
        
        # Asegurar que response sea string
        if not isinstance(response, str):
            response = str(response)
        
        # Step 4: Response generated
        yield trajectory.trajectory_metadata(
            title="✅ Job ID generated",
            content=f"Job submitted to IBM Quantum ({len(response)} characters)\n\n**Content:**\n- Job ID for tracking\n- Backend used\n- Execution configuration"
        )
        
        print("=" * 80)
        print(f"✅ [Computing Agent] Response generated ({len(response)} chars)")
        print("=" * 80)
        
        # Create the response message
        response_message = AgentMessage(text=response)
        
        # Yield the response to the user.
        yield response_message
        
    except Exception as e:
        import traceback
        error_msg = f"❌ Error in Computing Agent: {explain_error(e)}"
        error_details = f"\n\nError type: {type(e).__name__}\n"
        error_details += f"Details: {explain_error(e)}\n\n"
        error_details += "Traceback:\n"
        error_details += traceback.format_exc()

        # Error trajectory
        yield trajectory.trajectory_metadata(
            title="❌ Error detected",
            content=f"**Type:** {type(e).__name__}\n**Message:** {explain_error(e)}\n\nCheck logs for more details."
        )
        
        print("=" * 80)
        print(f"🔴 [Computing Agent] {error_msg}")
        print(error_details)
        print("=" * 80)
        
        yield AgentMessage(text=error_msg)

def run():
    """Starts the Quantum Computing Agent server with persistent storage"""
    port = int(os.getenv("COMPUTING_PORT", 8003))
    host = os.getenv("COMPUTING_HOST", "127.0.0.1")
    
    print("=" * 80)
    print("🚀 Starting Quantum Computing Agent Server (AgentStack)")
    print("=" * 80)
    print(f"  ⚡ Agent: Quantum Computing Agent")
    print(f"  🤖 Model: {model_name('COMPUTING')}")
    print(f"  🌐 Host: {host}")
    print(f"  🔌 Port: {port}")
    print(f"  🛠️  Tools: 1 (IBM Quantum Executor)")
    print(f"  📚 History: Persistent storage enabled (PlatformContextStore)")
    print(f"  🎯 Trajectory: Visualization enabled")
    print(f"  📚 Skills: Circuit Execution")
    print("=" * 80)
    print("\n💡 Tip: This agent is invoked by the Lab Agent (port 8000)")
    print("   to execute quantum circuits on IBM Quantum.")
    print("=" * 80)
    
    # Run server without PlatformContextStore (invoked via A2A)
    server.run(
        host=host,
        port=port
    )

if __name__ == "__main__":
    run()
