# PawPal+ Pet Care AI

PawPal+ is now a profile-driven Pet Care AI rather than a manual task scheduler.

The upgraded app uses:

- `Amazon Bedrock` for structured Claude task recommendations
- `local retrieval` over curated pet-care documents for grounding
- `deterministic guardrails` to block unsupported or unsafe advice
- recurring routine generation for `daily`, `weekly`, `monthly`, and condition-based care
- a derived daily schedule and in-app reminder view
- `logging + evaluation` to make system behavior traceable and testable

## Problem

Pet owners often know their pet needs structure, but struggle to translate age, breed/species traits, special needs, and changing situations into a realistic care routine. PawPal+ helps by generating grounded daily, weekly, and monthly care tasks, surfacing reminders, and explaining why the plan makes sense for that pet.

This makes the app useful for:

- senior pets needing low-impact routines
- pets on special diets or medication reminders
- owners who want condition-aware routines without manually building task lists
- users who want explanations for why tasks were recommended

## System Flow

The main pipeline is:

`pet profile + breed/custom species context + inferred traits + age context -> retrieve local care guidance -> Claude recommends recurring care tasks -> validator blocks unsafe or ungrounded advice -> app groups routines into daily/weekly/monthly sections -> app shows reminders, rationale, warnings, and logs`

### Components

- `app.py`
  Streamlit UI for pet profile setup, AI care-plan generation, daily scheduling, reminders, and evidence.

- `pawpal_system.py`
  Core deterministic domain model and scheduler. This remains the planning backbone.

- `ai_retrieval.py`
  Local retrieval layer over the repo's curated knowledge base in `knowledge_base/`.

- `bedrock_client.py`
  Amazon Bedrock Converse wrapper that requests strictly structured JSON recommendations from Claude on Bedrock.

- `ai_validation.py`
  Guardrails for groundedness, schema checks, time validation, and unsafe-advice blocking.

- `pawpal_ai.py`
  Orchestration layer that ties retrieval, Claude, validation, logging, and scheduling together.

- `ai_logging.py`
  Writes per-run JSON traces to `logs/`.

- `evaluate_ai_system.py`
  Structured experiment runner for repeatable reliability checks across multiple scenarios.

## Trust and Safety Design

PawPal+ is designed to be explainable and constrained instead of acting like an unrestricted chatbot.

- The model receives retrieved care guidance and is instructed to stay inside that evidence.
- Recommendations must include source IDs, rationale, time, priority, and frequency.
- The validator blocks:
  unsupported source citations,
  malformed times,
  invalid priorities or durations,
  diagnosis-like claims,
  medication dosage changes,
  advice that tries to replace veterinary care.
- The app logs retrieved passages, raw recommendations, blocked items, accepted tasks, and the final schedule plan.

This means Claude can help reason, but deterministic code still decides what is acceptable.

## Knowledge Base

The local retrieval set currently includes:

- `puppy_kitten_routine.md`
- `senior_pet_support.md`
- `kidney_diet_care.md`
- `medication_and_safety.md`
- `enrichment_and_monitoring.md`

These documents are intentionally local and curated so the demo is reproducible and the reasoning path is easy to explain.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Configure AWS credentials before using the AI features. The recommended local workflow is AWS CLI or an existing named profile:

```bash
aws configure
```

Set the Bedrock region. Optional overrides are shown below:

```bash
export AWS_REGION="us-west-2"
export AWS_PROFILE="default"
export BEDROCK_MODEL_ID="global.anthropic.claude-haiku-4-5-20251001-v1:0"
```

You can also enter `AWS region`, `AWS profile`, and a model ID in the Streamlit sidebar. The app does not ask for AWS secret keys directly.

## Run the App

```bash
streamlit run app.py
```

### Recommended demo flow

1. Create a pet profile with species, optional breed for dogs/cats, custom species for `Other`, age, and special-needs guidance.
2. Add an optional current situation or concern.
3. Click `Generate Pet Care Plan`.
4. Review the daily schedule, weekly care, monthly care, and condition-based guidance.
5. Check in-app reminders, blocked items, evidence, and reliability score.

## Reliability Evaluation

Run the unit tests:

```bash
python -m pytest -q
```

Run the live evaluation harness:

```bash
python evaluate_ai_system.py
```

The evaluation script runs multiple realistic scenarios, repeats them, and reports:

- average reliability score
- groundedness pass/fail
- consistency across repeated runs
- blocked recommendation counts
- accepted task summaries

It also saves a JSON report into `logs/`.

## Current Automated Coverage

The repo includes tests for:

- existing scheduler behavior
- retrieval relevance
- validator blocking of unsafe or ungrounded recommendations
- AI orchestration with a fake Bedrock client
- replacement of stale AI tasks while preserving manual tasks
- pet age-context reasoning, breed/custom-species validation, and inferred traits

Current test status:

- `65 passing tests`

## Public Interface Changes

`Task` now supports additional AI-related metadata:

- `ai_generated`
- `rationale`
- `confidence_score`
- `source_ids`
- `validation_status`

These fields are persisted in `data.json` so AI-generated tasks remain explainable after reload.

## Limitations

- The retrieval layer is lexical and local, not embedding-based.
- The app is a planning assistant, not a medical diagnosis tool.
- Live evaluation requires valid AWS credentials, Bedrock model access, and network access.
- The current UI focuses on one active pet profile in Streamlit, even though the scheduler model still supports multiple pets.
- The fixed default model is `global.anthropic.claude-haiku-4-5-20251001-v1:0`; if your account or region does not have access, choose another Bedrock Claude model ID you are enabled for.
- Live chat is not implemented yet, but the planner/provider architecture is designed to support a future chat extension.

## Architecture Summary

PawPal+ now demonstrates four applied-AI ideas in one system:

- `RAG`
  recommendations are grounded in retrieved pet-care documents

- `Reasoning`
  Claude converts pet context and evidence into structured task proposals

- `Guardrails`
  deterministic validators block unsafe or unsupported output

- `Reliability testing`
  unit tests, run logs, and scenario-based evaluation make the system inspectable
