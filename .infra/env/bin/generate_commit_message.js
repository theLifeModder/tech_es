const { execFileSync, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const TEMPLATE_RELATIVE_PATH = path.join(
  '.infra',
  'env',
  'config',
  'commit-message-template',
);
const SKIPPED_DIRECTORY_NAMES = new Set(['.git', 'node_modules']);

function gitRoot(directory) {
  const result = spawnSync(
    'git',
    ['-C', directory, 'rev-parse', '--show-toplevel'],
    { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] },
  );
  if (result.error) {
    throw new Error(`Unable to run Git: ${result.error.message}`);
  }
  if (result.status !== 0) {
    return null;
  }
  return result.stdout.trim();
}

function discoverRepositories(workspaceRoot) {
  const root = gitRoot(workspaceRoot);
  if (!root) {
    throw new Error(`Not inside a Git repository: ${workspaceRoot}`);
  }

  const roots = new Set([root]);
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    if (!entry.isDirectory() || SKIPPED_DIRECTORY_NAMES.has(entry.name)) {
      continue;
    }
    const nestedRoot = gitRoot(path.join(root, entry.name));
    if (nestedRoot && nestedRoot !== root) {
      roots.add(nestedRoot);
    }
  }
  return [...roots];
}

function stagedFiles(repositoryRoot) {
  const output = execFileSync(
    'git',
    ['-C', repositoryRoot, 'diff', '--cached', '--name-only', '-z'],
    { encoding: 'buffer' },
  );
  return output
    .toString('utf8')
    .split('\0')
    .filter(Boolean)
    .sort((left, right) => left.localeCompare(right));
}

function formatCompactFiles(files) {
  const directories = new Set();
  for (const file of files) {
    directories.add(path.posix.dirname(file));
  }

  const coveredDirectories = [];
  for (const directory of [...directories].sort(
    (left, right) => left.split('/').length - right.split('/').length ||
      left.localeCompare(right),
  )) {
    if (
      coveredDirectories.some(
        (parent) =>
          parent === '.' ||
          directory.startsWith(`${parent}/`),
      )
    ) {
      continue;
    }
    coveredDirectories.push(directory);
  }

  return coveredDirectories
    .sort((left, right) => left.localeCompare(right))
    .map((directory) =>
      directory === '.' ? '{proj}/*' : `{proj}/${directory}/*`,
    )
    .join(', ');
}

function formatFilePath(file) {
  return `{proj}/${file}`;
}

function formatDate(date = new Date()) {
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${month}${day}${date.getFullYear()}`;
}

function stripTemplateComments(template) {
  let output = '';
  let cursor = 0;

  while (cursor < template.length) {
    const opening = template.indexOf('///', cursor);
    if (opening === -1) {
      output += template.slice(cursor);
      break;
    }

    output += template.slice(cursor, opening);
    const closing = template.indexOf('///', opening + 3);
    if (closing === -1) {
      break;
    }

    const comment = template.slice(opening, closing + 3);
    output += comment.match(/\r\n|\r|\n/g)?.join('') || '';
    cursor = closing + 3;
  }

  const prefixComment = output.indexOf('//<');
  if (prefixComment !== -1 && output.indexOf('//<', prefixComment + 3) === -1) {
    output = output.slice(prefixComment + 3);
  }

  return output.replace(/\/\/[^\r\n]*/g, '');
}

function selectTemplate(templateFile, repositoryName) {
  const uncommentedTemplate = stripTemplateComments(templateFile);
  const lines = uncommentedTemplate.match(/[^\n]*\n|[^\n]+$/g) || [];
  const sections = new Map();
  let currentSection = null;

  for (const line of lines) {
    const marker = /^[ \t]*%%template::?([^%]+)%%[ \t]*(?:\r?\n)?$/.exec(line);
    if (marker) {
      currentSection = marker[1].trim();
      if (sections.has(currentSection)) {
        throw new Error(`Duplicate template section: ${currentSection}`);
      }
      sections.set(currentSection, '');
    } else if (currentSection !== null) {
      sections.set(currentSection, sections.get(currentSection) + line);
    }
  }

  if (sections.size === 0) {
    return templateFile;
  }
  if (sections.has(repositoryName)) {
    return sections.get(repositoryName);
  }
  if (sections.has('all')) {
    return sections.get('all');
  }
  throw new Error(
    `No commit message template for repository "${repositoryName}" ` +
      'and no template::all fallback was found.',
  );
}

function renderTemplate(template, files, date = new Date()) {
  const values = {
    'nate-date': formatDate(date),
    'staged-files': files.join(', '),
    'staged-files-compact': formatCompactFiles(files),
  };

  return template.replace(/%%([^%]+)%%/g, (tag, name) => {
    if (Object.hasOwn(values, name)) {
      return values[name];
    }

    const indexedTag = /^(staged-files(?:-compact)?)\[(\d+)\]$/.exec(name);
    if (!indexedTag) {
      return tag;
    }

    const [, listName, indexText] = indexedTag;
    const index = Number(indexText) - 1;
    const file = index >= 0 && index < files.length ? files[index] : '';
    if (listName === 'staged-files-compact') {
      return file ? formatFilePath(file) : '';
    }
    return file;
  });
}

function copyToClipboard(text) {
  const command =
    '$ErrorActionPreference = "Stop"; ' +
    '$encoded = [Console]::In.ReadLine(); ' +
    'if ($null -eq $encoded) { exit 1 }; ' +
    '$text = [Text.Encoding]::UTF8.GetString(' +
    '[Convert]::FromBase64String($encoded)); ' +
    'Set-Clipboard -Value $text; ' +
    '$copied = Get-Clipboard -Raw; ' +
    'if ($copied -cne $text) { throw "Clipboard verification failed." }';
  const encoded = Buffer.from(text, 'utf8').toString('base64');
  const result = spawnSync(
    'powershell.exe',
    ['-NoProfile', '-NonInteractive', '-STA', '-Command', command],
    { input: encoded, encoding: 'utf8' },
  );

  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(
      result.stderr.trim() || 'PowerShell could not copy the message to the clipboard.',
    );
  }
}

function main() {
  const workspaceRoot = path.resolve(process.argv[2] || process.cwd());
  const printOnly = process.argv.includes('--print-only');
  const repositories = discoverRepositories(workspaceRoot);
  const withStagedFiles = repositories
    .map((repositoryRoot) => ({
      repositoryRoot,
      files: stagedFiles(repositoryRoot),
    }))
    .filter(({ files }) => files.length > 0);

  if (withStagedFiles.length === 0) {
    throw new Error('No staged files found in the workspace Git repositories.');
  }
  if (withStagedFiles.length > 1) {
    throw new Error(
      'Staged files were found in more than one Git repository. ' +
        'Stage changes in only the repository whose message you are preparing.',
    );
  }

  const { repositoryRoot, files } = withStagedFiles[0];
  const templatePath = path.join(repositories[0], TEMPLATE_RELATIVE_PATH);
  if (!fs.existsSync(templatePath)) {
    throw new Error(`Commit message template not found: ${templatePath}`);
  }

  const templateFile = fs.readFileSync(templatePath, 'utf8');
  const template = selectTemplate(
    templateFile,
    path.basename(repositoryRoot),
  );
  const message = renderTemplate(template, files);
  if (printOnly) {
    process.stdout.write(message);
    return;
  }

  copyToClipboard(message);
  console.log(`Commit message copied to clipboard for ${repositoryRoot}.`);
}

if (require.main === module) {
  try {
    main();
  } catch (error) {
    console.error(`ERROR: ${error.message}`);
    process.exitCode = 1;
  }
}

module.exports = {
  formatCompactFiles,
  formatFilePath,
  formatDate,
  renderTemplate,
  selectTemplate,
  stripTemplateComments,
};
