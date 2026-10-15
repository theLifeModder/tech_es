# Commit Message Template

This extension recognizes files named `commit-message-template` and provides
syntax highlighting without requiring workspace settings.

## Install

To build the installable VSIX from this directory:

```sh
npx --yes @vscode/vsce package
```

Install the generated `.vsix` in VS Code with **Extensions: Install from
VSIX...**. Syntax highlighting uses the active color theme's standard TextMate
scopes. To use the included colors, select **Commit Message Template** from
**Preferences: Color Theme**; this optional theme uses green valid tags, red
invalid tags, gray comments, and white template text.

The workspace settings in the parent `.vscode/settings.json` assign the template
colors after the extension is installed.

## Recognized syntax

- Valid tags: `%%nate-date%%`, `%%staged-files%%`,
  `%%staged-files-compact%%`, their positive or zero-numbered indexed forms,
  and line-only `%%template::name%%` / `%%template:name%%` section markers.
- Invalid `%%...%%` tags use the standard `invalid.illegal` scope.
- `//` comments out the rest of a line.
- `///` begins or ends a block comment. Without a closing `///`, it comments
  through the end of the file.
- `//<` marks the boundary after a leading comment; text before it is shown as
  a comment.
