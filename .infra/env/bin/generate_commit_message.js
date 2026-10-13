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
  const groups = new Map();
  for (const file of files) {
    const directory = path.posix.dirname(file);
    const group = groups.get(directory) || [];
    group.push(path.posix.basename(file));
    groups.set(directory, group);
  }

  return [...groups.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([directory, names]) => {
      const prefix = directory === '.' ? '{proj}/' : `{proj}/${directory}/`;
      return `${prefix}${names.join(';')}`;
    })
    .join(', ');
}

function formatDate(date = new Date()) {
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${month}${day}${date.getFullYear()}`;
}

function renderTemplate(template, files, date = new Date()) {
  const values = {
    'nate-date': formatDate(date),
    'staged-files': files.join(', '),
    'staged-files-compact': formatCompactFiles(files),
  };

  return template.replace(/%%([^%]+)%%/g, (tag, name) =>
    Object.hasOwn(values, name) ? values[name] : tag,
  );
}

function copyToClipboard(text) {
  const command =
    '$ErrorActionPreference = "Stop"; ' +
    '$encoded = [Console]::In.ReadLine(); ' +
    'if ($null -eq $encoded) { exit 1 }; ' +
    'Set-Clipboard -Value ([Text.Encoding]::UTF8.GetString(' +
    '[Convert]::FromBase64String($encoded)))';
  const encoded = Buffer.from(text, 'utf8').toString('base64');
  const result = spawnSync(
    'powershell.exe',
    ['-NoProfile', '-NonInteractive', '-Command', command],
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
  const templatePath = path.join(repositoryRoot, TEMPLATE_RELATIVE_PATH);
  if (!fs.existsSync(templatePath)) {
    throw new Error(`Commit message template not found: ${templatePath}`);
  }

  const template = fs.readFileSync(templatePath, 'utf8');
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

module.exports = { formatCompactFiles, formatDate, renderTemplate };
