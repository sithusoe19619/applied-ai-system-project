# PawPal+ Final Project Reflection

## 1. System Design

For the final version of PawPal+, I redesigned the project from a manual pet-task scheduler into an applied AI system that helps a pet owner generate and understand a care plan.

The three core user actions are now:

1. **Create a pet profile** — The user enters the owner name, pet name, species, optional breed or custom species, age, and any special-needs or vet-guidance notes. This gives the AI the profile context it needs to reason about the pet.
2. **Generate an AI care plan** — The system retrieves local pet-care knowledge, asks Bedrock for species-aware planning help, validates the output, and turns accepted recommendations into a structured care plan with daily, weekly, monthly, and condition-based sections.
3. **Ask follow-up questions in chat** — The user can open a dedicated `Chat with PawPal AI` page to ask broader questions about the pet, the current situation, or the generated plan. The chat uses the current profile or active result when available.

### Initial design vs final design

The earlier version of PawPal+ centered on `Owner`, `Pet`, `Task`, and `Scheduler` as a deterministic scheduling app. That structure still exists, but the final system adds an AI layer on top of it rather than replacing it.

The final design is built around these responsibilities:

- **`pawpal_system.py`** — The deterministic backbone. It stores pets and tasks, interprets lifespan and life-stage context, and still owns the scheduling behavior.
- **`ai_retrieval.py`** — Retrieves relevant local pet-care passages from the knowledge base before generation.
- **`bedrock_client.py`** — Wraps Amazon Bedrock calls for three different AI behaviors: species profiling, structured plan generation, and free-form chat.
- **`pawpal_ai.py`** — Orchestrates the planning pipeline: species profiling, retrieval, Bedrock recommendation generation, validation, logging, and scheduling.
- **`ai_validation.py`** — Applies guardrails that block unsafe or unsupported outputs before they become visible tasks.
- **`pawpal_chat.py`** — Builds contextual chat prompts using the current profile or active plan result.
- **`app.py` + `planner.py` + `pages/Results.py` + `pages/Chat.py`** — Split the UI into a hidden-navigation entrypoint, a planner page, a results page, and a separate chat page.

### Most important design changes

The biggest design shift was moving from “the user manually adds tasks” to “the AI proposes tasks from context and deterministic code decides what is acceptable.” That changed the project from a scheduler utility into a full applied AI workflow.

Other important changes were:

- I added **retrieval** so the model has local pet-care evidence before generating a plan.
- I added a **species profile step** so lifespan and care traits can differ across animals instead of using one generic default for every non-dog/non-cat pet.
- I added **guardrails and validation** so the model output is checked for grounding, allowed frequencies, durations, time formats, and unsafe medical-style language.
- I added a **dedicated AI chat page** so the system is not only a one-shot planner, but also a follow-up reasoning assistant.
- I changed the UI to a **session-based multipage flow** so the planner form, generated result, and chat feel like parts of one system rather than one crowded screen.

## 2. Applied AI System Behavior

### How the AI pipeline works

The final planning flow is:

`pet profile -> species profile lookup -> retrieval from local knowledge base -> Bedrock care-plan generation -> validation / guardrails -> scheduling -> logging -> results page`

I also added a separate conversational flow:

`current profile or current AI result -> contextual chat prompt -> Bedrock chat reply -> safety fallback if needed`

This means the AI does not just answer a question in isolation. It first uses the pet profile, then uses retrieved information, then generates a structured output, and finally passes through deterministic checks.

### Applied AI features implemented

This project now clearly includes:

- **Retrieval-Augmented Generation (RAG)** — The planner retrieves relevant pet-care passages from a local knowledge base before generating recommendations.
- **Agentic / multi-step workflow** — The system performs multiple steps in sequence: species profiling, retrieval, plan generation, validation, scheduling, logging, and optional chat follow-up.
- **Reliability / testing system** — The project includes unit tests, run logging, blocked-output tracking, and a scenario-based evaluation harness.

I did **not** implement fine-tuning. Instead, I focused on combining retrieval, orchestration, validation, and explainability to make the system stronger and more trustworthy.

## 3. Trustworthiness and Responsible Design

I wanted the system to feel useful without pretending to be a veterinarian. The final version is intentionally constrained.

The main trust and safety decisions were:

- The planner uses **retrieved local documents** instead of relying only on the model’s internal knowledge.
- Recommendations must include **source IDs, rationale, cadence, and timing**.
- The validator blocks outputs that are **ungrounded, malformed, or medically unsafe**.
- The system blocks or refuses advice that tries to **diagnose, prescribe, change dosage, or replace veterinary care**.
- Each AI planning run is logged with the **query, retrieved passages, raw recommendations, blocked items, accepted tasks, and schedule output**.

I think this is one of the strongest parts of the project because the AI is not treated like a magic black box. The model helps reason and draft outputs, but deterministic code still controls what becomes part of the final artifact.

## 4. AI Collaboration

I used AI heavily during design, coding, debugging, and polishing, but the most useful pattern was not “generate code immediately.” The most useful pattern was asking the AI to help me make better engineering decisions and then verifying those decisions against the real codebase.

The most effective ways I used AI were:

- **Architecture and decomposition** — I used AI to break the project into retrieval, generation, validation, logging, evaluation, and UI responsibilities instead of trying to keep everything in one file.
- **Prompt and workflow design** — AI helped shape the species-profile step, the planner prompt, the cadence-control flow, and the later chat feature.
- **Testing support** — AI helped create focused tests around validation, cadence enforcement, Bedrock response parsing, and contextual chat behavior.
- **Debugging and iteration** — AI was especially useful when Bedrock returned malformed JSON, when prompt instructions conflicted with user input, and when the UI flow needed to be split across separate pages.

I still had to use judgment. For example, several times I rejected or revised behavior that looked technically valid but did not match the product intent. One example was when the app initially treated custom species too rigidly and rejected realistic values like `Monkey`. Another was when cadence instructions such as `weekly only` were being passed as weak extra context instead of strong constraints. In both cases, I had to push the implementation toward what the user experience actually needed rather than accepting the first technically plausible result.

## 5. Testing and Reliability

The project now has a much broader testing story than the original scheduler.

The automated test suite covers:

- core scheduler behavior
- breed and species context behavior
- retrieval relevance
- Bedrock response parsing
- validation and guardrails
- orchestration of species profiling, retrieval, planning, and replacement of old AI tasks
- cadence restriction handling like `weekly only`
- contextual chat behavior and unsafe chat fallback

The repo currently has **69 passing tests**.

In addition to the unit tests, the project also has a live evaluation script that runs multiple Bedrock-backed scenarios and reports:

- reliability averages
- grounding checks
- consistency across repeated runs
- blocked-output behavior for unsafe scenarios
- cadence compliance
- plan-shape validity

This matters because a system like this should not only “work once.” It should also be inspectable, repeatable, and safe enough to justify trust.

## 6. What Went Well

The best outcome was that the project stopped feeling like a small class exercise and started feeling like a real applied AI artifact. The combination of retrieval, validation, logging, and multipage UI gave the system a stronger identity than a simple chatbot or a basic scheduler.

I also think the separation between deterministic code and model behavior worked well. The model is used for reasoning and generation, but the rest of the system provides structure, constraints, and explainability.

The dedicated chat feature was another strong addition because it turned the app from a one-time generator into something more interactive and useful.

## 7. What I Would Improve Next

If I had another iteration, I would improve three things first:

1. **Stronger evaluation metrics and reporting** — The evaluation harness is useful, but I would continue improving it so the reliability evidence is even easier to cite in a demo or report.
2. **Richer knowledge base / retrieval quality** — The current retrieval layer is local and lexical. It is good for reproducibility, but an embedding-based retrieval system would likely improve recall and relevance.
3. **More structured chat controls** — The chat is useful, but I would add clearer conversation modes such as “Explain my plan,” “Ask a general pet-care question,” and “Help me revise the plan safely.”

## 8. Key Takeaway

The biggest lesson from this project was that an applied AI system is not just “call a model and show the answer.” The useful system is everything around the model: the context gathering, retrieval, validation, logging, UI design, and testing.

The final version of PawPal+ is stronger because the model is only one part of the workflow. The surrounding system is what makes the AI output understandable, safer, and more trustworthy.
