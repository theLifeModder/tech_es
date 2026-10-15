const assert = require('node:assert/strict');
const { test } = require('node:test');

const { formatCompactFiles } = require('./generate_commit_message.js');

/** Keep a root-level staged file literal when other repository files are unstaged. */
test('lists an individual root file unless the repository is fully staged', function testRootFileRemainsExact() {
  assert.equal(
    formatCompactFiles(
      ['.gitignore'],
      ['.gitignore', 'README.md', 'src/app.js'],
    ),
    '{proj}/.gitignore',
  );
});

/** Combine staged root-level siblings under a single project prefix. */
test('groups staged files with the same root parent using semicolons', function testRootSiblingFilesAreGrouped() {
  assert.equal(
    formatCompactFiles(
      ['.gitignore', 'README.md'],
      ['.gitignore', 'README.md', 'src/app.js'],
    ),
    '{proj}/.gitignore;README.md',
  );
});

/** Compact a directory only when every Git-visible file beneath it is staged. */
test('uses a folder wildcard when every file in that folder is staged', function testFullyStagedFolderUsesWildcard() {
  assert.equal(
    formatCompactFiles(
      ['docs/guide.md', 'docs/reference.md'],
      ['.gitignore', 'docs/guide.md', 'docs/reference.md', 'src/app.js'],
    ),
    '{proj}/docs/*',
  );
});

/** Keep paths exact when any file in their directory has not been staged. */
test('keeps paths exact when a folder has unstaged files', function testPartialFolderStaysExact() {
  assert.equal(
    formatCompactFiles(
      ['docs/guide.md'],
      ['docs/guide.md', 'docs/reference.md'],
    ),
    '{proj}/docs/guide.md',
  );
});

/** Combine staged sibling filenames even if their parent folder is not complete. */
test('groups staged sibling files when another file in their folder is unstaged', function testPartialFolderSiblingFilesAreGrouped() {
  assert.equal(
    formatCompactFiles(
      ['docs/guide.md', 'docs/reference.md'],
      ['docs/guide.md', 'docs/reference.md', 'docs/draft.md'],
    ),
    '{proj}/docs/guide.md;reference.md',
  );
});

/** Use the project-root wildcard only when every Git-visible project file is staged. */
test('uses the project wildcard only when all project files are staged', function testEntireRepositoryUsesWildcard() {
  const files = ['.gitignore', 'docs/guide.md'];

  assert.equal(formatCompactFiles(files, files), '{proj}/*');
});

/** Compact complete directories while preserving exact paths from partial ones. */
test('combines complete-directory wildcards with exact paths from other folders', function testMixedFoldersUseAppropriatePaths() {
  assert.equal(
    formatCompactFiles(
      ['docs/guide.md', 'docs/reference.md', 'src/app.js'],
      [
        '.gitignore',
        'docs/guide.md',
        'docs/reference.md',
        'src/app.js',
        'src/config.js',
      ],
    ),
    '{proj}/docs/*, {proj}/src/app.js',
  );
});

/** Group siblings in partial directories alongside complete-directory wildcards. */
test('groups sibling names while retaining wildcards for complete directories', function testMixedGroupingAndWildcards() {
  assert.equal(
    formatCompactFiles(
      ['docs/guide.md', 'docs/reference.md', 'src/app.js', 'src/readme.md'],
      [
        '.gitignore',
        'docs/guide.md',
        'docs/reference.md',
        'src/app.js',
        'src/readme.md',
        'src/config.js',
      ],
    ),
    '{proj}/docs/*, {proj}/src/app.js;readme.md',
  );
});
