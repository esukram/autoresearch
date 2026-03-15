# Domain Strategies

This document defines optimization strategies for different domains. The `strategy_hint` field in eval.json selects the appropriate strategy.

## Strategy: `coverage-improvement`

**Goal:** Increase test coverage to a target percentage.

**Analysis approach:**
- Run coverage report with per-file breakdown
- Identify files with lowest coverage
- Identify untested functions and branches
- Prioritize: uncovered functions > uncovered branches > uncovered lines

**Hypothesis patterns:**
- "Adding a test for `<function>` in `<file>` will increase coverage by ~N%"
- "Testing the error path in `<function>` will cover the uncovered branch at line N"
- "Adding a parametrized test for `<function>` will cover multiple input scenarios"

**Common pitfalls:**
- Writing tests that technically cover lines but don't assert meaningful behavior
- Ignoring error paths (they're often the least covered)
- Testing trivial getters/setters instead of business logic
- Breaking existing tests while adding new ones

**Target file patterns:** `tests/**/*.py`, `**/*_test.go`, `**/*.test.ts`

**Protected file patterns:** Source code files (when only adding tests), config files, lock files

---

## Strategy: `performance-optimization`

**Goal:** Reduce latency, memory usage, or resource consumption.

**Analysis approach:**
- Run benchmarks to identify bottlenecks
- Profile hot paths
- Look for: N+1 queries, unnecessary allocations, missing caching, synchronous I/O in hot paths
- Measure before and after each change

**Hypothesis patterns:**
- "Caching the result of `<expensive_call>` will reduce average latency by ~Nms"
- "Replacing the O(n²) loop in `<function>` with a hash lookup will reduce processing time"
- "Batching the N database queries in `<handler>` into one query will reduce response time"
- "Adding an index on `<column>` will speed up the `<query>` by ~Nms"

**Common pitfalls:**
- Premature optimization of cold paths
- Introducing caching bugs (stale data, cache invalidation)
- Breaking correctness for speed
- Optimizing the benchmark instead of the code

**Target file patterns:** Route handlers, data access layers, middleware, hot-path functions

**Protected file patterns:** Tests, config, lock files, migration files

---

## Strategy: `test-hardening`

**Goal:** Add edge case tests, boundary conditions, and error handling tests.

**Analysis approach:**
- Review existing tests for coverage gaps
- Identify boundary conditions: empty inputs, max values, null/undefined, concurrent access
- Look for error paths without tests
- Check for missing negative tests (inputs that should fail)

**Hypothesis patterns:**
- "Adding a test for empty input to `<function>` will catch the unhandled edge case"
- "Testing `<function>` with MAX_INT will expose the overflow bug"
- "Adding a concurrent access test will verify thread safety of `<component>`"
- "Testing the timeout path in `<function>` will cover the error handling branch"

**Common pitfalls:**
- Adding edge case tests that duplicate existing coverage
- Writing brittle tests that depend on implementation details
- Testing edge cases without understanding the expected behavior
- Forgetting to test both the happy path and the error path for each edge case

**Target file patterns:** Test files matching the project's test file pattern

**Protected file patterns:** Source code (when only hardening tests), config files

---

## Strategy: `code-quality`

**Goal:** Improve linting scores, reduce complexity, eliminate warnings.

**Analysis approach:**
- Run linter with full output
- Categorize issues by type and severity
- Prioritize: errors > warnings > style issues
- Group related issues that can be fixed together

**Hypothesis patterns:**
- "Extracting the nested conditional in `<function>` into a guard clause will reduce complexity"
- "Replacing the `any` types in `<file>` with proper types will fix N type errors"
- "Breaking `<large_function>` into smaller functions will reduce cyclomatic complexity"

**Common pitfalls:**
- Fixing lint warnings in ways that change behavior
- Introducing new warnings while fixing others
- Over-abstracting to reduce complexity metrics
- Changing public APIs to fix style issues

**Target file patterns:** Source files matching the linter's scope

**Protected file patterns:** Test files, config files, generated files

---

## Strategy: `feature-completion`

**Goal:** Implement features until acceptance tests pass.

**Analysis approach:**
- Read failing acceptance tests to understand required behavior
- Map each failing test to a specific feature or behavior
- Determine implementation order (dependencies between features)
- Start with the simplest failing test

**Hypothesis patterns:**
- "Implementing the `<method>` handler will make the `<test>` acceptance test pass"
- "Adding the `<field>` validation will satisfy the `<test>` requirement"
- "Connecting the `<component>` to the `<service>` will enable the `<test>` flow"

**Common pitfalls:**
- Implementing features in the wrong order (dependencies)
- Over-engineering features beyond what the test requires
- Breaking passing tests while implementing new features
- Adding dead code that doesn't contribute to passing tests

**Target file patterns:** Source files for the feature being implemented

**Protected file patterns:** Test/spec files (they define the goal), config files

---

## Strategy: `custom`

**Goal:** User-defined optimization with explicit strategy hints.

When `strategy_hint` is `custom`, the eval.json should include an additional `strategy_description` field in config:

```json
{
  "config": {
    "strategy_hint": "custom",
    "strategy_description": "Reduce the number of SQL queries per request by batching related queries. Focus on the /api/users and /api/orders endpoints. Do not modify the ORM models, only the service layer."
  }
}
```

The agent follows the custom description as its primary strategy guide, falling back to general optimization principles for anything not specified.

**Analysis approach:**
- Read the `strategy_description` carefully to identify explicit constraints, priorities, and scope boundaries
- Identify the measurable metrics implied by the description (e.g., query count, response time, file size)
- Map the description to concrete files and code regions
- If the description is vague, focus on the evals — they define the real success criteria

**Hypothesis patterns:**
- "Applying `<technique from strategy_description>` to `<file>` will improve `<metric>` toward the eval threshold"
- "Refactoring `<component>` as described in the strategy will make `<eval_id>` pass"
- "The strategy description mentions `<constraint>`, so limiting changes to `<scope>` and applying `<approach>` should improve results"
- "Combining the strategy hint with eval failure output suggests `<specific change>` in `<file>`"

**Common pitfalls:**
- Ignoring explicit constraints in the strategy description (e.g., "do not modify X")
- Over-interpreting vague descriptions — let the evals be the ground truth
- Applying generic optimization techniques that contradict the custom strategy
- Treating custom like a blank check — the description + evals define the bounds

**Target file patterns:** Determined by `strategy_description` — typically the files and directories explicitly mentioned

**Protected file patterns:** Any files excluded by the strategy description, plus standard protections (config, lock files, eval infrastructure)

---

## Cross-Strategy Guidelines

### Incremental Changes

Regardless of strategy, each iteration should make the **smallest change** that could produce an improvement. Large changes are:
- Harder to evaluate (which part helped?)
- More likely to cause regressions
- Harder to revert cleanly

### Diversifying Approaches

If the same type of hypothesis has been tried N times without progress, switch approaches:

1. **Same file, different approach** — Try a fundamentally different technique
2. **Different file, same approach** — Apply the working technique elsewhere
3. **Different eval, fresh start** — Focus on a different failing eval
4. **Step back and analyze** — Re-read the code and eval output for missed patterns

### Reading Failure Output

Before forming a hypothesis, **always read the full eval output**. The answer is usually in the error message:
- Stack traces point to the exact location
- Assertion messages describe the expected vs actual behavior
- Compiler errors identify the exact type mismatch
- Coverage reports show the exact uncovered lines
