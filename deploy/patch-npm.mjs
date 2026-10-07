// Compatible patch fixes for npm's bundled dependencies, not application code.
// npm's published archive omits internal docs workspaces, so reinstalling its
// complete development tree fails. Verify each archive and existing dependency
// constraints before replacing only the affected bundled package directories.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
const root = '/usr/local/lib/node_modules/npm/node_modules';
const require = createRequire('/usr/local/lib/node_modules/npm/package.json');
const semver = require('semver');
const patches = [
  {name: 'brace-expansion', before: '5.0.9', version: '5.0.12', engines: '20 || >=22',
    dependencies: {'balanced-match': '^4.0.2'},
    integrity: 'YovQ3rzhaLMIrDjNDMkNS01tea93qhEhG5xy8f6+R0l+dw3Ki+5sCoIoI942iuLZTHWogWktgwVDhU09iNEimQ=='},
  {name: 'undici', before: '6.28.0', version: '6.28.1', engines: '>=18.17', dependencies: {},
    integrity: 'zWpdTVD54H48CIybL0rWQ3ukpb9d23wM7eH5RtfdmeP70cWHNjtfo7P4vZX+5CoDcO53J4Pu5uXp7lNfjc6DRA=='},
];
function directories(folder, output = []) {
  for (const entry of fs.readdirSync(folder, {withFileTypes: true})) {
    if (!entry.isDirectory()) continue; // Never follow symlinks outside the tree.
    const target = path.join(folder, entry.name);
    if (fs.existsSync(path.join(target, 'package.json'))) output.push(target);
    directories(target, output);
  }
  return output;
}
const packages = directories(root);
for (const patch of patches) {
  if (!semver.satisfies(process.versions.node, patch.engines)) throw Error('Incompatible Node engine');
  const targets = packages.filter(target => JSON.parse(fs.readFileSync(path.join(target, 'package.json'))).name === patch.name);
  if (!targets.length) throw Error(`Expected bundled package missing: ${patch.name}`);
  const response = await fetch(`https://registry.npmjs.org/${patch.name}/-/${patch.name}-${patch.version}.tgz`, {signal: AbortSignal.timeout(60000)});
  if (!response.ok) throw Error('Patch download failed');
  const data = Buffer.from(await response.arrayBuffer());
  if (crypto.createHash('sha512').update(data).digest('base64') !== patch.integrity) throw Error('Patch integrity mismatch');
  const archive = `/tmp/npm-security-${patch.name}.tgz`;
  fs.writeFileSync(archive, data);
  const members = execFileSync('tar', ['-tzf', archive], {encoding: 'utf8'}).trim().split('\n');
  if (members.some(name => !name.startsWith('package/') || name.split('/').includes('..'))) throw Error('Unsafe patch archive');
  for (const target of targets) {
    const existing = JSON.parse(fs.readFileSync(path.join(target, 'package.json')));
    if (existing.version !== patch.before) throw Error(`Unexpected bundled version: ${patch.name}`);
    for (const [dependency, range] of Object.entries(patch.dependencies)) {
      const local = createRequire(path.join(target, 'package.json'));
      let folder = path.dirname(local.resolve(dependency));
      let installed;
      while (folder.startsWith('/usr/local/lib/node_modules/npm/')) {
        const metadata = path.join(folder, 'package.json');
        if (fs.existsSync(metadata)) {
          const candidate = JSON.parse(fs.readFileSync(metadata));
          if (candidate.name === dependency) { installed = candidate; break; }
        }
        folder = path.dirname(folder);
      }
      if (!installed) throw Error('Patch dependency missing');
      if (installed.name !== dependency || !semver.satisfies(installed.version, range)) throw Error('Patch dependency mismatch');
    }
    if (!target.startsWith(root + '/')) throw Error('Unsafe patch destination');
    fs.rmSync(target, {recursive: true});
    fs.mkdirSync(target);
    execFileSync('tar', ['-xzf', archive, '-C', target, '--strip-components=1']);
  }
  fs.unlinkSync(archive);
  console.log(`Patched npm bundled ${patch.name} ${patch.before} -> ${patch.version}; copies=${targets.length}`);
}
