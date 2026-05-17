# Agent Instructions

## Code Style

- Keep code straightforward and beginner-readable.
- Do not use fancy syntax sugar when a clear ordinary form is easier to read.
- Do not compress conditional logic into one-line `if` / `else` expressions.
- Write `if` / `else` branches on separate lines with explicit blocks.
- Add a short line comment above each meaningful logic block explaining what the block does.
- Add Javadoc or the language-equivalent doc comment for every public method, function, class, and important internal helper.
- Prefer descriptive names over abbreviations.
- Avoid clever abstractions unless they remove real duplication or make the system easier to reason about.

## Change Management

- Commit by logical step, not by arbitrary time slices.
- Create PRs by milestone.
- Agents may create commits and open PRs when a milestone or coherent logical step is complete.
- Agents must not merge PRs by themselves.
- When refactoring or deleting meaningful code, make a dedicated commit when the change is substantial enough to review independently.

## File Deletion Policy

- Do not permanently delete files with `rm`.
- Move files that would otherwise be deleted into `Archive/`.
- Keep `Archive/` ignored by git.
- If a file is moved to `Archive/`, mention it in the final summary.
