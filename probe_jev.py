from typesafe_sdk import Choice, Noul

from jev_orchestrator.connection import create_jev_client

client = create_jev_client()
response = client.system_one(
    state={"task": "Find the latest Klipper documentation and summarize the relevant extruder sensor configuration."},
    questions={
        "agent": Choice(instructions="Which agent should handle this task?", criteria={
            "luna_scout": "Cheap retrieval and initial research",
            "sol_researcher": "Complex research and synthesis",
            "astra_architect": "Exceptional reasoning only",
        }),
        "needs_web": Noul(instructions="Does this task require current web research?"),
    },
)
print("model=", response.model)
print("agent=", response.answers["agent"].choice)
print("agent_probs=", response.answers["agent"].probabilities)
print("needs_web=", response.answers["needs_web"].noul)
print("usage=", response.usage)
