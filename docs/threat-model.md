# Threat model

Status: draft v0.1 (2026-10-25). Research notes that refine it live in `docs/research/`.

## What Hackproof protects

The **integrity of the reward signal** of an RL environment or benchmark task: the reward should
be high only when the task was actually solved. Two consequences follow:

- in training, a task that pays for something other than the skill teaches that something else and
  wastes compute;
- in evaluation, a task that can be passed without solving it makes published scores meaningless.

Hackproof gives evidence about this integrity. It does not prove it.

## Actors

| Actor | Assumed behaviour |
| --- | --- |
| Policy under training or evaluation | Optimises reward by any available means. Has full control of its sandbox within the privileges the task grants, reads anything readable there, writes arbitrary files and output. Not assumed malicious, but assumed to find any path that pays. |
| Task author | Honest and competent, but fallible. Usually tests that the reference solution passes, rarely that wrong solutions fail. |
| Hackproof operator | Runs Hackproof on tasks they did not write. Task code is untrusted. |

## Trust boundaries

1. **Agent sandbox → grader.** The grader must depend only on the artifact it is meant to judge
   (an answer file, a diff, a final state), never on state the agent could change for other
   reasons.
2. **Task assets → agent sandbox.** Tests, reference solutions and expected outputs must not be
   reachable from the sandbox during the episode, including through version history, image layers,
   environment variables, caches or the network.
3. **Agent output → LLM judge.** Text written by the agent is data, never instructions to the judge.
4. **Task code → Hackproof host.** Hackproof itself never runs task code on the host.

## Properties checked

| # | Property | Method | Main limitation |
| --- | --- | --- | --- |
| P1 | Trivial baselines earn zero reward | Run fixed baseline agents (no-op, empty, echo, format-only) | Catches only defects a trivial agent can reach |
| P2 | Grader isolation | Static review of task configuration; filesystem diff after the episode; clean-room re-grading of the artifact in a fresh environment | Clean-room re-grading needs a well-defined artifact |
| P3 | No answer leakage | Search the sandbox, image layers, environment and version history for copies of tests, reference solution and expected outputs; report network policy | Finds copies, not paraphrases |
| P4 | Grader strictness | Mutation testing of the reference solution; kill rate with a confidence interval | Equivalent mutants inflate survivor counts |
| P5 | Reference determinism | Repeated clean runs of the reference; Wilson interval and SPRT on the failure rate | Rare flakes need many runs |
| P6 | Judge robustness | Paired scoring of known-good and known-bad answers before and after content-neutral changes | Coverage limited to the transformations tested |
| P7 | Difficulty calibration | Beta posterior on a model's pass rate; SPRT for "too hard / too easy" | Relative to one model; needs paid model runs |

Verdicts are `ok`, `warn`, `fail` or `unknown`. `unknown` means the evidence is insufficient; it is
reported, never rounded to `ok`.

## Out of scope

- Escapes from the container runtime or kernel, hardware side channels, and host security in
  general.
- Whether the task instruction is clear, fair or representative of a real skill.
- Training dynamics: how much a defect actually changes a trained model.
- Proof of absence: passing every check does not make a task hack-proof. The name is a goal.

## Hackproof's own safety rules

- Task code runs only inside containers, never on the host.
- The task directory is mounted read-only; nothing else from the host is mounted.
- Network is off by default and enabled only when the task's own configuration requires it, and
  this is recorded in the report.
- CPU, memory and wall-time limits on every container.
- Containers and volumes are removed after each run.

## Disclosure

Findings in third-party tasks are reported privately to their authors first, with a suggested fix
and a 14-day window, before any public mention. Public reports contain aggregate statistics and
already-fixed or author-approved examples, never instructions for abusing a specific task.
