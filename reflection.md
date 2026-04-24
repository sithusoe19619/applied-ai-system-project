# Paw'Pal Pet Care AI Reflection and Ethics

Building Paw'Pal Pet Care AI taught me that responsible AI is not just about getting a good-looking answer. It is about making the system grounded, testable, and safe enough that a user can understand what it is doing and where its limits are.

## 1. What are the limitations or biases in my system?

The biggest limitation in my system is that it depends on local retrieval. Paw'Pal Pet Care AI uses a curated local knowledge base and lexical retrieval, so the quality of the plan depends on whether the right information exists in those documents. If the knowledge base is incomplete, the output can still sound confident while missing an important edge case.

There is also a built-in bias toward common household pet-care routines. The system is much better at creating safe, structured daily or weekly care plans than handling rare medical situations or unusual species-specific cases. That was an intentional trade-off because I designed it as a pet-care planning assistant, not as a veterinary diagnosis tool.

## 2. Could my AI be misused, and how would I prevent that?

Yes. The most obvious misuse would be asking the system for diagnosis, dosage changes, emergency treatment advice, or instructions that replace a veterinarian. A user could also misuse it by treating a generated care plan as medical authority instead of guidance.

I tried to prevent that in two ways. First, I added deterministic validation rules that block unsafe recommendations, including diagnosis language, prescription-style advice, dosage changes, emergency-treatment guidance, and suggestions to ignore or replace a veterinarian. Second, I kept a human in the loop: the app only generates plans and chat responses for review, and it does not take any automatic action on behalf of the user.

## 3. What surprised me while testing my AI's reliability?

What surprised me most was how easy it was for the system to sound correct while still being wrong in a subtle way. During testing, I saw outputs that looked polished but did not fully respect an important user constraint like cadence or context. That made me realize that fluency is not the same thing as reliability.

Because of that, I treated validation and testing as core parts of the product. The project now has `102 passing tests`, plus an evaluation script and run logging. The biggest lesson for me was that AI reliability improves when outputs are checked against rules for grounding, structure, cadence, and safety instead of being trusted just because they read well.

## 4. How did I collaborate with AI during this project?

I used AI during brainstorming, architecture planning, debugging, prompt refinement, and test development. The most productive collaboration happened when I used AI to explore options quickly, then verified the good ideas against the actual code and behavior of the system.

One helpful AI suggestion was decomposing the system into clear responsibilities: retrieval, model generation, validation, logging, evaluation, and UI. That suggestion made the codebase easier to organize and helped turn the project into a real applied AI workflow instead of a single prompt wrapped in a UI.

One flawed AI suggestion was treating user instructions like `weekly only` as soft context instead of a strict requirement. That approach could still produce plausible output, but it did not match the product behavior I wanted. I fixed that by enforcing cadence constraints more directly in the planning and validation flow.

## 5. What would I improve next?

If I continued this project, I would improve three things first. I would make the evaluation reporting easier to summarize in a demo, so reliability evidence is more visible than a raw test pass count. I would also improve retrieval quality beyond a purely local lexical approach, because that is one of the main limits on relevance and coverage today.

I would also make the chat experience more structured. Right now it is useful, but it would be stronger with clearer modes like explaining the current plan, asking a general care question, or revising a routine safely.

## Final Reflection

This project changed how I think about AI systems. The model itself matters, but the real quality comes from the surrounding system: retrieval, validation, logging, testing, and human review. It also taught me that problem-solving in AI is not just about getting technically correct output. Several times, I had to revise the system until the behavior matched what a user would actually need.

The biggest takeaway I will carry forward is that responsible AI is not just about making something impressive. It is about making something constrained, inspectable, and trustworthy enough to use carefully, while balancing engineering quality, AI capability, and user trust.
