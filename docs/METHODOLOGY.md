# Methodology

This note explains how the evaluator scores responses and why LLM-as-judge was chosen over other ways of measuring LLM output.

## What needed measuring

The agents under test answer users from retrieved documents while following a system prompt full of rules: what to say, what never to say, and what to do when the answer isn't in the documents. A useful evaluation had to answer four questions for each response:

1. Did it answer what was asked?
2. Was the tone right?
3. Did it stay inside the retrieved context, or did it make things up?
4. Did it obey every rule in the system prompt?

It also had to explain its scores, list the specific rules that were broken, and be usable by QA engineers without a data science setup.

## Options considered

**Reference-based metrics (BLEU, ROUGE, METEOR, Levenshtein distance).** These compare a response with a known correct answer by word or character overlap. They are fast and well understood, but agent conversations rarely have one correct wording, and these metrics know nothing about RAG context or system prompt rules. They return a number with no explanation.

**Embedding similarity (BERTScore, MoverScore).** These measure meaning rather than exact wording, which is an improvement, but they still need a reference answer and still can't tell you that a response broke a guardrail.

**Trained evaluator models (NLI classifiers, BLEURT, Prometheus).** These are purpose-built for judging quality and can be consistent. They usually need a reference answer or a fixed rubric, and self-hosting a 13B-parameter judge needs GPU infrastructure that a QA team typically doesn't have.

**Research frameworks (G-Eval).** G-Eval showed that an LLM with chain-of-thought prompting correlates well with human judgment. As published, it is a method rather than a tool, and its scoring relies on token probabilities that most hosted APIs don't expose.

**Evaluation platforms (RAGAS, LangSmith, DeepEval, TruLens).** These are mature and well documented, with strong RAG metrics, dashboards and CI integration. They expect programmatic access to the agent and its retrieval pipeline, a Python environment, and in some cases a specific framework such as LangChain. Their output is aimed at developers.

**LLM-as-judge with a structured rubric (chosen).** A capable general-purpose model scores each response against defined criteria and returns strict JSON. It needs no reference answer, it reads the RAG context and system prompt directly, it explains every score, and it lists violations by name. It runs from a browser with only an API key.

## How the judge is set up

- **Rubric:** four dimensions, each scored 0–100 with written reasoning. Groundedness is scored only when RAG context is supplied, and system prompt adherence only when a system prompt is supplied.
- **Hallucination rule:** if the response matches the supplied context, the judge must treat it as grounded and must not flag it as invented.
- **Guardrail extraction:** the judge first lists every instruction it finds in the system prompt, then checks the response against each one, so missed rules are visible.
- **Determinism:** temperature 0 and a strict JSON schema. Output that isn't valid JSON is rejected with a clear error instead of being partially parsed.
- **Actionable output:** each result includes suggested improvements to the response and refinements to the prompt, which feed straight back into prompt tuning.

## Known limits

- An LLM judge can be wrong or inconsistent. Borderline scores, especially in the 76–85 warning band, should get a human review.
- Different judge models score differently. In my testing, Claude was the most critical and the most specific about violations, which is why it is the recommended evaluator.
- The judge sees only what it is given. If the RAG context passed in is incomplete, groundedness scores will be too.

## Phased approach

1. **Human-assisted (current).** QA collects prompt and response pairs, scores them in batch, and reviews flagged violations to refine system prompts.
2. **Semi-automated.** With API access to the agent, prompts are sent and responses collected automatically. QA reviews exceptions and borderline scores, and a regression suite with a pass or fail gate is established.
3. **Fully automated.** Playwright drives the full loop: prompt submission, response capture, scoring and reporting. Scores are tracked across releases and alerts fire on regressions.
