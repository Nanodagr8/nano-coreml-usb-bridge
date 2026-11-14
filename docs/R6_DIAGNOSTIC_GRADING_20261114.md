# R6 offline diagnostic grading

The diagnostic component is implemented and qualified against **20/20 deterministic synthetic fixtures**. This is an offline engineering milestone: no new model requests were made, no historical R5 answers were recovered/rescored, and no coding-quality or productivity estimate is added.

R5's strict scores remain CPU 4/12, GPU candidate 3/12 and iPhone 4/12. Its raw answers were not retained. This component can diagnose newly supplied text under declared rules; it cannot explain those earlier failed answers after the fact.

## What the component reports

| Classification | Meaning |
| --- | --- |
| `exact_match` | The bounded text passes the frozen AST/JSON reference rule. |
| `code_fence_normalized` | Removing one complete enclosing fence makes it pass; the strict result stays false. |
| `wrapper_rejected` | Prose with fences, multiple fences, wrong-language fences or incomplete wrapping is not extracted. Strict result is unassessed. |
| `python_noncanonical` | Valid parsed expression differs structurally from the reference. Semantic correctness is unassessed. |
| `json_value_mismatch` | Parsed JSON differs under canonical, type-sensitive comparison. |
| `invalid_syntax` / `invalid_json` / `empty_output` | The bounded candidate is malformed or empty. |
| `resource_limit` / worker failure labels | Processing was rejected/stopped; strict result is unassessed. |

`normalized_pass` means only that this limited normalization passes the same reference rubric. It does not establish semantic equivalence, general coding correctness or permission to execute the answer. Different valid algorithms and bugs can both be `python_noncanonical`. Boolean/integer and integer/float distinctions remain explicit in JSON scoring.

The frozen R5 task protocol is checked by SHA-256 before its cases are used. A standard-library-only implementation of its reference rule is checked against the original R5 grader for processed test cases. The live R5 module is not imported by the isolated worker, because its transport dependency needs user-site packages. Original R5 source/protocol/evidence files remain unchanged.

## Processing boundaries

- The parent rejects oversized/non-UTF-8 input before launch. Input is capped at 4,096 UTF-8 bytes; larger character counts are rejected before encoding/hashing.
- Candidate text travels through stdin, never process arguments. The worker uses isolated Python startup, disables bytecode writes, and inherits only four OS/temporary-directory environment variables. Credentials and model configuration are not passed through.
- Before AST/JSON parsing: at most 256 lexical tokens, nesting 24 and numeric-token length 64. Python ASTs are then limited to 512 nodes and depth 64.
- Each worker communication has a two-second timeout. Timeout/pipe failures kill and drain the owned child with a further one-second cleanup allowance. Process creation itself and OS scheduling are not covered by an absolute end-to-end deadline; a cleanup failure reports `worker_failed` rather than claiming success.
- Candidate code is never compiled for execution, evaluated, imported or run. AST parsing is a parsing operation, not a code-execution sandbox. No OS memory quota or general-purpose sandbox certification is claimed.
- The parent accepts only fixed diagnostic fields and labels and verifies the input hash/length. Raw answer text, file paths and arbitrary exception/worker output are excluded from returned diagnostics.

Python documents that AST parsing can exhaust parser resources; lexical bounds and an isolated timeout are layered controls, not proof of universal parser safety. The documented subprocess cleanup pattern requires killing and finishing communication after a timeout. See the official [AST documentation](https://docs.python.org/3/library/ast.html) and [subprocess documentation](https://github.com/python/cpython/blob/main/Doc/library/subprocess.rst). These behaviors were tested on local Python 3.14.0; version-specific newer API parameters are not used.

## Five integrations used

GitHub supplied live scope/evidence, Context7 supplied official cleanup documentation, Exa located primary parser documentation, Code Tytor: Python provided supplementary source review, and Mermaid Chart rendered the implemented boundaries. [Tool checks](../results/r6_tool_checks_20261114.json) record all five successful calls. They are supporting tools, not an automatically configured pipeline. The review tool returned zero issues; that is advisory and is not independent security certification.

## Reproduce

```text
python -m unittest discover -s tests -v
python client/r6_diagnostic_grading.py
python client/r6_diagnostic_grading.py --qualify
python client/r6_diagnostic_grading.py --case-id py_inclusive_range --text-file PRIVATE_TEXT_FILE
```

Dry mode launches no worker. Qualification uses only the public synthetic fixtures in [the component](../client/r6_diagnostic_grading.py). The committed [qualification metadata](../results/r6_diagnostic_fixtures_20261114.json) is deterministic and source-bound. A fixture pass means the expected diagnostic label was returned, not that a model answered a task correctly. Tests cover malicious-looking but unexecuted input, strict-rule agreement, wrapper ambiguity, JSON types, input/lexical/AST bounds, credential exclusion, timeout/pipe cleanup, malformed worker output and metadata redaction.

A new live diagnostic study would need its own frozen protocol and separate evidence. Independent reproduction, semantic/behavioral assessment, sustained coding/build quality, model parity, operator/energy instrumentation, physical reliability and release gates remain open. R3-R5 conclusions, model/service configuration and parallel iOS work are separate from this offline milestone.
