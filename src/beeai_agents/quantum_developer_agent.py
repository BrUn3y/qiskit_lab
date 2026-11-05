"""
Quantum Developer Agent - Expert in Quantum Code Development

This agent is a specialist in:
- Qiskit code generation
- OpenQASM 3.0 code generation
- Explanation of quantum computing concepts
- Creation of quantum circuit examples
- Quantum code optimization
- Documentation of quantum algorithms

Model: configurable via DEVELOPER_MODEL (Ollama/Watsonx)
Port: 8001
Type: AgentStack Server with A2A (ReActAgent without tools)
"""

import asyncio
import json
import os
import re
from urllib import request as urllib_request

from typing import Annotated
from collections.abc import AsyncGenerator

from a2a.types import AgentSkill, Message
from a2a.utils.message import get_message_text
from agentstack_sdk.server import Server
from agentstack_sdk.server.context import RunContext
from agentstack_sdk.server.store.platform_context_store import PlatformContextStore
from agentstack_sdk.a2a.types import AgentMessage
from agentstack_sdk.a2a.extensions import AgentDetail, AgentDetailTool
from agentstack_sdk.a2a.extensions import TrajectoryExtensionServer, TrajectoryExtensionSpec

from beeai_framework.agents.react import ReActAgent
from beeai_framework.backend.message import UserMessage
from beeai_framework.memory import UnconstrainedMemory

from .model_config import create_chat_model, explain_error, model_name, run_agent_with_retries

# Specialized instructions for the Developer Agent
DEVELOPER_INSTRUCTIONS = """You are an Expert in Quantum Code Development and Quantum Algorithms with deep knowledge in Qiskit and OpenQASM.

⚠️ CRITICAL RULE: READ CAREFULLY what the user asks for. If they ask for "Grover's algorithm", generate Grover's algorithm, NOT a Bell state.

YOUR SPECIALTY:
- Generate clean and efficient Qiskit code
- Create valid OpenQASM 2.0 and 3.0 code
- Implement classical quantum algorithms (Grover, Shor, Deutsch-Jozsa, etc.)
- Explain quantum computing concepts with clarity and detail
- Provide practical examples of quantum circuits
- Optimize circuits to reduce gates and depth
- Document code with helpful comments

QASM 2.0 CODE FORMAT:
```qasm
OPENQASM 2.0;
include "qelib1.inc";
qreg q[N];
creg c[N];
// Quantum gates
h q[0];
cx q[0],q[1];
// Measurements
measure q -> c;
```

QISKIT CODE FORMAT:
```python
from qiskit import QuantumCircuit

qc = QuantumCircuit(N, N)
qc.h(0)
qc.cx(0, 1)
qc.measure_all()
```

IMPORTANT RULES:
1. ⚠️ **READ CAREFULLY** what the user asks - DO NOT confuse algorithms
2. ALWAYS include "OPENQASM 2.0" and "include" in QASM code
3. Define qreg and creg before using qubits
4. ALWAYS include measurements (measure)
5. Use descriptive names in comments
6. Explain the purpose of the circuit/algorithm
7. Mention practical applications
8. Suggest optimizations when relevant

# 📚 QUANTUM ALGORITHM KNOWLEDGE

You have deep knowledge of the following classical quantum algorithms. When requested, GENERATE the code from your knowledge, DO NOT use templates:

## 🔍 Grover's Algorithm (Quantum Search)
- **Purpose**: Search in unstructured database with quadratic acceleration O(√N)
- **Key components**:
  1. Initialization: Uniform superposition of all states
  2. Oracle: Marks the target state (inverts its phase)
  3. Grover Diffuser: Amplifies the amplitude of the marked state
  4. Iterations: Repeat oracle + diffuser approximately √N times
- **Quantum advantage**: O(√N) vs classical O(N)
- **Practical applications**: Database search, optimization, cryptanalysis

## 🔐 Deutsch-Jozsa Algorithm
- **Purpose**: Determine if a boolean function is constant or balanced
- **Key components**:
  1. Preparation: Qubits in superposition + auxiliary qubit in |1⟩
  2. Oracle: Implements the function f(x)
  3. Interference: Hadamard on input qubits
  4. Measurement: If result is |0...0⟩ → constant, otherwise → balanced
- **Quantum advantage**: 1 query vs classical N/2+1
- **Practical applications**: Demonstration of quantum supremacy, function analysis

## 🎲 Bernstein-Vazirani Algorithm
- **Purpose**: Find a secret binary string s in a function f(x) = s·x
- **Key components**:
  1. Preparation: Similar to Deutsch-Jozsa
  2. Oracle: Implements f(x) = s·x (dot product)
  3. Interference: Hadamard reveals the string s directly
- **Quantum advantage**: 1 query vs classical n queries
- **Practical applications**: Cryptography, quantum communication

## 🔄 Quantum Fourier Transform (QFT)
- **Purpose**: Quantum analog of the Discrete Fourier Transform
- **Key components**:
  1. Hadamard on each qubit
  2. Controlled phase rotations (cp gates)
  3. Qubit swap for correct order
- **Quantum advantage**: O(n²) vs classical O(n·2ⁿ)
- **Practical applications**: Shor's algorithm, phase estimation, quantum simulation

## 🔢 Shor's Algorithm (Factorization)
- **Purpose**: Factorize integers in polynomial time
- **Key components**:
  1. Superposition preparation
  2. Quantum modular exponentiation
  3. Inverse QFT to find the period
  4. Classical post-processing
- **Quantum advantage**: Polynomial vs classical exponential
- **Practical applications**: RSA cryptanalysis, number theory

## ⚡ Simon's Algorithm
- **Purpose**: Find the period of a function with hidden symmetry
- **Key components**:
  1. Superposition of states
  2. Oracle that implements f(x) = f(x⊕s)
  3. Hadamard for interference
  4. Multiple measurements to solve system of equations
- **Quantum advantage**: Exponential vs classical
- **Practical applications**: Precursor of Shor, cryptanalysis

## 🎯 Amplitude Amplification Algorithm
- **Purpose**: Generalization of Grover to amplify amplitudes
- **Key components**:
  1. State preparation operator
  2. Reflection operator over the target state
  3. Reflection operator over the initial state
- **Practical applications**: Optimization, quantum machine learning, quantum Monte Carlo

# 📖 FUNDAMENTAL BASIC CIRCUITS

You know these basic circuits (generate the code when requested):

- **Bell State**: Maximum entanglement of 2 qubits (H + CNOT)
- **GHZ State**: Entanglement of n qubits (H + multiple CNOT)
- **W State**: Another type of multipartite entanglement
- **Quantum Teleportation**: Quantum state transfer using entanglement
- **Superdense Coding**: Send 2 classical bits with 1 qubit
- **Swap Test**: Compare two quantum states
- **Phase Kickback**: Fundamental technique for oracles

# 🎯 RESPONSE GUIDE ACCORDING TO REQUEST

## When asked for a specific ALGORITHM:

⚠️ **CRITICAL RULE**: If requested "Grover's algorithm", generate Grover's algorithm. If requested "Deutsch-Jozsa algorithm", generate Deutsch-Jozsa. DO NOT confuse algorithms.

**Response structure for algorithms:**

1. **Title and description** (2-3 paragraphs):
   - What the algorithm does
   - Why it is important
   - Quantum advantage it offers

2. **Full QASM code**:
   - With explanatory comments
   - All algorithm sections marked

3. **Step-by-step explanation**:
   - What each section does
   - Why it is necessary

4. **Expected results**:
   - What measurements to expect
   - How to interpret results

5. **Practical applications**:
   - Where this algorithm is used
   - Problems it solves

## When asked to "Create a circuit":

- Generate complete and functional QASM code
- Include explanatory comments
- Mention the purpose of the circuit

## When asked to "Explain [concept]":

⚠️ IMPORTANT: DO NOT just say "Here is the explanation"

YOU MUST INCLUDE:
- ✅ Detailed explanation of the concept (minimum 3-4 paragraphs)
- ✅ QASM code example demonstrating the concept
- ✅ Description of how the code works
- ✅ Practical applications
- ✅ Expected results

CORRECT RESPONSE EXAMPLE:
```
# 🔬 Bell State - Quantum Entanglement

A Bell state is one of the four maximally entangled quantum states 
of two qubits. These states are fundamental in...

[Detailed 3-4 paragraph explanation]

## 💻 Example Code

```qasm
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];        // Creates superposition
cx q[0],q[1];  // Entangles the qubits
measure q -> c;
```

## 🎯 How It Works

1. The Hadamard gate (h) creates a superposition...
2. The CNOT gate (cx) entangles the qubits...

## 📊 Expected Results

When measuring, you will get 50% |00⟩ and 50% |11⟩...
```

## When asked to "Optimize":

- Analyze the current code
- Suggest specific improvements
- Provide optimized code

## When asked for "Example of":

- Complete commented code
- Step-by-step explanation
- Use cases

# ⚠️ CRITICAL RULES

1. **READ THE REQUEST CAREFULLY**
   - If asked for "Grover" → generate Grover
   - If asked for "Bell state" → generate Bell state
   - If asked for "Deutsch-Jozsa" → generate Deutsch-Jozsa
   - DO NOT confuse different algorithms

2. **NEVER RESPOND WITH GENERIC MESSAGES**
   
   ❌ INCORRECT:
   "Here is the explanation for Grover's algorithm..."
   
   ✅ CORRECT:
   [Full 3-4 paragraph explanation on Grover]
   [Complete code for Grover's algorithm]
   [Detailed description of how it works]

3. **ALWAYS PROVIDE COMPLETE CONTENT**
   - Explanations: Minimum 3-4 paragraphs
   - Code: Complete and executable
   - Examples: With comments and explanation

4. **STRUCTURE YOUR RESPONSES**
   - Use markdown headings (##, ###)
   - Use code blocks with syntax highlighting
   - Use lists and emojis for clarity

5. **STANDARD RESPONSE FORMAT**:
   ```
   # [Algorithm/Concept Title]
   
   [Detailed explanation - 3-4 paragraphs]
   
   ## 💻 Code
   
   ```qasm
   [Full code of requested algorithm]
   ```
   
   ## 🎯 Code Explanation
   
   [Step-by-step description of each section]
   
   ## 📊 Expected Results
   
   [What to expect when running]
   
   ## 🚀 Applications
   
   [Practical use cases]
   ```

REMEMBER:
- Your value is in providing COMPLETE and DETAILED explanations
- ALWAYS generate the algorithm or circuit the user requested
- DO NOT confuse different quantum algorithms
"""

# Agent details for AgentStack
DEVELOPER_AGENT_DETAIL = AgentDetail(
    user_greeting="👨‍💻 Hello! I'm the Quantum Developer Agent. I'm an expert in generating quantum code (Qiskit/QASM), explaining quantum computing concepts, and creating classical quantum algorithms like Grover, Shor, Deutsch-Jozsa, and more.",
    version="1.0.0",
    framework="BeeAI + A2A (Watsonx/Ollama)",
    author={"name": "Edgar Bruney"},
    tools=[
        AgentDetailTool(
            name="Quantum Code Generation",
            description="Generates QASM 2.0/3.0 and Qiskit code for quantum circuits and algorithms."
        ),
        AgentDetailTool(
            name="Quantum Concepts Explanation",
            description="Explains quantum computing concepts with code examples and practical applications."
        ),
        AgentDetailTool(
            name="Algorithm Implementation",
            description="Implements classical quantum algorithms: Grover, Shor, Deutsch-Jozsa, Bernstein-Vazirani, QFT, Simon, etc."
        )
    ],
)

# Skills exposed by the agent
DEVELOPER_AGENT_SKILLS = [
    AgentSkill(
        id="quantum-code-generation",
        name="Quantum Code Generation",
        description="Generates complete and functional quantum code in QASM and Qiskit with detailed explanations.",
        tags=["Quantum Computing", "Code Generation", "QASM", "Qiskit"],
        examples=[
            "Create a superposition circuit with 3 qubits",
            "Generate a Bell state circuit in QASM",
            "Implement Grover's algorithm for 3 qubits",
            "Create a QFT circuit for 4 qubits",
            "Generate code for quantum teleportation"
        ]
    ),
    AgentSkill(
        id="quantum-explanations",
        name="Quantum Concepts Explanation",
        description="Explains quantum computing concepts with practical examples and executable code.",
        tags=["Quantum Computing", "Education", "Explanations"],
        examples=[
            "Explain what quantum entanglement is",
            "What is quantum superposition?",
            "Explain how Grover's algorithm works",
            "What is the quantum Fourier transform?",
            "Explain the difference between a qubit and a classical bit"
        ]
    ),
    AgentSkill(
        id="quantum-algorithms",
        name="Quantum Algorithm Implementation",
        description="Implements classical quantum algorithms with full code and step-by-step explanations.",
        tags=["Quantum Computing", "Algorithms", "Grover", "Shor", "Deutsch-Jozsa"],
        examples=[
            "Implement Grover's algorithm",
            "Create Deutsch-Jozsa algorithm",
            "Generate Bernstein-Vazirani algorithm",
            "Implement Shor's algorithm",
            "Create an amplitude amplification circuit"
        ]
    )
]

# Create the Agent Stack server.
server = Server()

_SUPERPOSITION_PATTERN = re.compile(r"\b(superposition|superposici[oó]n)\b", re.IGNORECASE)
_QUBIT_COUNT_PATTERN = re.compile(r"\b(\d+)\s*[- ]?\s*(?:qubits?|c[uú]bits?)\b", re.IGNORECASE)
_CODE_REQUEST_PATTERN = re.compile(
    r"\b(create|generate|build|implement|circuit|qasm|crea\w*|genera\w*|"
    r"constru\w*|implementa\w*|circuito)\b",
    re.IGNORECASE,
)
_BELL_PATTERN = re.compile(r"\b(bell(?:\s+state)?|estado\s+de\s+bell)\b", re.IGNORECASE)
_CX_PATTERN = re.compile(r"\b(cx|cnot|controlled[- ]?not|compuerta\s+cx)\b", re.IGNORECASE)
_GROVER_PATTERN = re.compile(r"\bgrover(?:'s)?\b", re.IGNORECASE)
_DEUTSCH_JOZSA_PATTERN = re.compile(r"\bdeutsch[- ]?jozsa\b", re.IGNORECASE)
_CONCEPT_REQUEST_PATTERN = re.compile(
    r"\b(explain\w*|describe\w*|what (?:is|are)|explica\w*|qu[eé] (?:es|son))\b",
    re.IGNORECASE,
)
_ENTANGLEMENT_PATTERN = re.compile(r"\b(entanglement|entrelazamiento)\b", re.IGNORECASE)


def _superposition_qasm(request: str) -> str | None:
    """Build a simple measured superposition circuit without an LLM round trip."""
    if not _SUPERPOSITION_PATTERN.search(request):
        return None
    match = _QUBIT_COUNT_PATTERN.search(request)
    qubit_count = int(match.group(1)) if match else 1
    if not 1 <= qubit_count <= 64:
        return None
    gates = "\n".join(f"h q[{index}];" for index in range(qubit_count))
    return (
        "```qasm\n"
        "OPENQASM 2.0;\n"
        'include "qelib1.inc";\n'
        f"qreg q[{qubit_count}];\n"
        f"creg c[{qubit_count}];\n\n"
        f"{gates}\n"
        "measure q -> c;\n"
        "```"
    )


def _basic_algorithm_qasm(request: str) -> tuple[str, str] | None:
    """Return reliable measured QASM for common introductory circuits."""
    if not _CODE_REQUEST_PATTERN.search(request):
        return None

    if _BELL_PATTERN.search(request):
        return "Bell state", """```qasm
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];

h q[0];
cx q[0],q[1];
measure q -> c;
```"""

    if _GROVER_PATTERN.search(request):
        match = _QUBIT_COUNT_PATTERN.search(request)
        qubit_count = int(match.group(1)) if match else 2
        if qubit_count not in (2, 3):
            return None
        phase_flip = (
            "cz q[0],q[1];"
            if qubit_count == 2
            else "h q[2];\nccx q[0],q[1],q[2];\nh q[2];"
        )
        return "Grover search", (
            "```qasm\n"
            "OPENQASM 2.0;\n"
            'include "qelib1.inc";\n'
            f"qreg q[{qubit_count}];\n"
            f"creg c[{qubit_count}];\n\n"
            "h q;\n\n"
            f"// Oracle: mark |{'1' * qubit_count}>\n{phase_flip}\n\n"
            "// Grover diffuser\nh q;\n"
            "x q;\n"
            f"{phase_flip}\n"
            "x q;\n"
            "h q;\n"
            "measure q -> c;\n"
            "```"
        )

    if _DEUTSCH_JOZSA_PATTERN.search(request):
        return "Deutsch-Jozsa", """```qasm
OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[2];

// Two input qubits and one ancilla; balanced parity oracle.
x q[2];
h q[0];
h q[1];
h q[2];
cx q[0],q[2];
cx q[1],q[2];
h q[0];
h q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];
```"""

    if _CX_PATTERN.search(request):
        return "CX gate", """```qasm
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];

// Prepare |10> in little-endian qubit order, then copy the control with CX.
x q[0];
cx q[0],q[1];
measure q -> c;
```"""

    return None


async def _run_concept_model(prompt: str) -> str:
    """Generate a concise concept explanation without exposing model reasoning."""
    configured_model = model_name("DEVELOPER")
    if configured_model.startswith("ollama:"):
        ollama_model = configured_model.split(":", 1)[1]
        ollama_url = os.getenv("OLLAMA_API_BASE", "http://127.0.0.1:11434").rstrip("/")
        payload = json.dumps(
            {
                "model": ollama_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,
                "options": {"num_predict": 220, "temperature": 0.1},
            }
        ).encode("utf-8")

        def send_request() -> str:
            req = urllib_request.Request(
                f"{ollama_url}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib_request.urlopen(req, timeout=180) as response:
                data = json.loads(response.read().decode("utf-8"))
            return str(data.get("message", {}).get("content", "")).strip()

        response = await asyncio.to_thread(send_request)
        if not response:
            raise ValueError("Ollama returned an empty concept explanation.")
        return response

    model_output = await create_chat_model("DEVELOPER").run(
        [UserMessage(prompt)],
        max_tokens=220,
        temperature=0.1,
    )
    return model_output.get_text_content()

def create_developer_agent():
    """Create the Quantum Developer Agent with its configured chat model."""
    llm = create_chat_model("DEVELOPER")
    
    # Use ReActAgent without tools (only for reasoning and code generation)
    return ReActAgent(
        llm=llm,
        tools=[],  # No tools - only code generation
        memory=UnconstrainedMemory(),
    )

@server.agent(
    name="Quantum Developer Agent",
    detail=DEVELOPER_AGENT_DETAIL,
    skills=DEVELOPER_AGENT_SKILLS
)
async def quantum_developer_agent(
    input: Message,
    context: RunContext,
    trajectory: Annotated[TrajectoryExtensionServer, TrajectoryExtensionSpec()]
):
    """
    Main handler for the Quantum Developer Agent.
    
    This agent generates quantum code and provides detailed explanations
    of quantum computing concepts and algorithms.
    """
    user_query = get_message_text(input)
    print("=" * 80)
    print(f"💻 [Developer Agent] Received query: '{user_query[:100]}...'")
    print("=" * 80)
    
    # Step 1: Request analysis
    yield trajectory.trajectory_metadata(
        title="🔍 Analyzing code request",
        content=f"Processing user query:\n```\n{user_query[:200]}{'...' if len(user_query) > 200 else ''}\n```"
    )

    basic_algorithm = _basic_algorithm_qasm(user_query)
    if basic_algorithm:
        algorithm_name, algorithm_qasm = basic_algorithm
        yield trajectory.trajectory_metadata(
            title=f"✅ {algorithm_name} circuit generated",
            content="Generated and measured a valid OpenQASM 2.0 circuit deterministically.",
        )
        yield AgentMessage(text=algorithm_qasm)
        return

    superposition_qasm = _superposition_qasm(user_query)
    if superposition_qasm:
        yield trajectory.trajectory_metadata(
            title="✅ Superposition circuit generated",
            content="Generated and measured a valid OpenQASM 2.0 circuit deterministically.",
        )
        yield AgentMessage(text=superposition_qasm)
        return
    
    # Create the agent with the instructions
    agent = create_developer_agent()
    
    # Step 2: Agent preparation
    yield trajectory.trajectory_metadata(
        title="🤖 Preparing development agent",
        content=f"**Configuration:**\n- Model: {model_name('DEVELOPER')}\n- Specialty: Quantum code generation\n- Memory: Unconstrained"
    )
    
    # Build the prompt with system instructions
    if _ENTANGLEMENT_PATTERN.search(user_query):
        full_prompt = (
            "You are a quantum computing educator. Explain quantum entanglement accurately and concisely. "
            "Use this exact canonical example: the Bell state |Phi+> = (|00> + |11>)/sqrt(2), "
            "created by applying H to qubit 0 and then CNOT with control 0 and target 1. "
            "Explain correlated measurements and explicitly state that entanglement cannot transmit "
            "information faster than light. Do not rename the Bell state or introduce a cryptography "
            "protocol unless the user asks for one. Answer in no more than 120 words.\n\n"
            f"USER REQUEST:\n{user_query}"
        )
    elif _CONCEPT_REQUEST_PATTERN.search(user_query):
        full_prompt = (
            "You are a quantum computing educator. Answer the request accurately and concisely. "
            "Define the concept, explain its mechanism, and give one useful quantum example. "
            "Do not generate code unless the user asks for it. Answer in no more than 120 words.\n\n"
            f"USER REQUEST:\n{user_query}"
        )
    else:
        full_prompt = f"{DEVELOPER_INSTRUCTIONS}\n\n---\n\nUSER REQUEST:\n{user_query}"
    
    # Step 3: Code generation
    yield trajectory.trajectory_metadata(
        title="⚙️ Generating quantum code",
        content="Agent is analyzing the request and generating QASM/Qiskit code..."
    )
    
    concept_request = bool(_CONCEPT_REQUEST_PATTERN.search(user_query))

    # Execute the agent
    try:
        if concept_request:
            response = await _run_concept_model(full_prompt)
        else:
            run_context = await run_agent_with_retries(agent, full_prompt)
        
        # Update trajectory with progress
        yield trajectory.trajectory_metadata(
            title="✅ Code generated",
            content="- [x] Analysis completed\n- [x] Code generated\n- [x] Explanation prepared"
        )
        
        # Extract the ReAct response for code-generation requests.
        if not concept_request:
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
            title="✅ Response ready",
            content=f"Code and explanation generated ({len(response)} characters)\n\n**Content:**\n- QASM/Qiskit code\n- Detailed explanation\n- Usage examples"
        )
        
        print("=" * 80)
        print(f"✅ [Developer Agent] Response generated ({len(response)} chars)")
        print("=" * 80)
        
        # Create the response message
        response_message = AgentMessage(text=response)
        
        # Yield the response to the user.
        yield response_message
        
    except Exception as e:
        import traceback
        error_msg = f"❌ Error in Developer Agent: {explain_error(e)}"
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
        print(f"🔴 [Developer Agent] {error_msg}")
        print(error_details)
        print("=" * 80)
        
        yield AgentMessage(text=error_msg)

def run():
    """Starts the Quantum Developer Agent server with persistent storage"""
    port = int(os.getenv("DEVELOPER_PORT", 8001))
    host = os.getenv("DEVELOPER_HOST", "127.0.0.1")
    
    print("=" * 80)
    print("🚀 Starting Quantum Developer Agent Server (AgentStack)")
    print("=" * 80)
    print(f"  👨‍💻 Agent: Quantum Developer Agent")
    print(f"  🤖 Model: {model_name('DEVELOPER')}")
    print(f"  🌐 Host: {host}")
    print(f"  🔌 Port: {port}")
    print(f"  🛠️  Tools: 0 (Pure LLM - Code Generation)")
    print(f"  📚 History: Persistent storage enabled (PlatformContextStore)")
    print(f"  🎯 Trajectory: Visualization enabled")
    print(f"  📚 Skills: Code Generation, Explanations, Algorithm Implementation")
    print("=" * 80)
    print("\n💡 Tip: This agent is invoked by the Lab Agent (port 8000)")
    print("   to generate quantum code and explanations.")
    print("=" * 80)
    
    # Run server without PlatformContextStore (invoked via A2A)
    server.run(
        host=host,
        port=port
    )

if __name__ == "__main__":
    run()
