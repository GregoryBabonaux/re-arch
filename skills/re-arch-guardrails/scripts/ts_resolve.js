#!/usr/bin/env node
/*
 * ts_resolve.js: exact module resolution for re-arch-scan using TypeScript's own
 * resolver (tsconfig per file incl. "extends", paths, baseUrl, moduleResolution,
 * package.json "exports", workspace symlinks).
 *
 * stdin:  {"root": "/abs/repo", "files": ["/abs/file.ts", ...], "typescript": "/abs/.../typescript.js"}
 * stdout: {"version": "5.x", "builtins": [...], "files": {"/abs/file.ts": [[spec, "/abs/target" | null], ...]}}
 *
 * Reads files only; never executes code from the repository.
 */
const fs = require('fs');
const path = require('path');

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const ts = require(input.typescript);
const root = input.root;
const builtins = require('module').builtinModules || [];

const configCache = new Map();
const resolutionCaches = new Map();

function findConfig(file) {
  let dir = path.dirname(file);
  while (dir.startsWith(root)) {
    for (const name of ['tsconfig.json', 'jsconfig.json']) {
      const p = path.join(dir, name);
      if (fs.existsSync(p)) return p;
    }
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return null;
}

function optionsFor(file) {
  const cfg = findConfig(file);
  const key = cfg || '<default>';
  if (configCache.has(key)) return configCache.get(key);
  let options = {
    allowJs: true, checkJs: false, jsx: ts.JsxEmit.Preserve, resolveJsonModule: true,
    moduleResolution: ts.ModuleResolutionKind.Bundler || ts.ModuleResolutionKind.NodeJs,
    module: ts.ModuleKind.ESNext,
  };
  if (cfg) {
    try {
      const parsed = ts.getParsedCommandLineOfConfigFile(cfg, {}, {
        ...ts.sys,
        onUnRecoverableConfigFileDiagnostic: () => {},
      });
      if (parsed && parsed.options) options = { ...options, ...parsed.options, allowJs: true };
    } catch (e) { /* keep defaults */ }
  }
  const entry = { options, cache: ts.createModuleResolutionCache(path.dirname(cfg || root), (x) => x, options) };
  configCache.set(key, entry);
  return entry;
}

function scriptText(file, text) {
  if (file.endsWith('.vue') || file.endsWith('.svelte') || file.endsWith('.astro')) {
    const blocks = [...text.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
    if (file.endsWith('.astro')) {
      const fm = text.match(/^---\n([\s\S]*?)\n---/);
      if (fm) blocks.push(fm[1]);
    }
    return blocks.join('\n');
  }
  return text;
}

const out = { version: ts.version, builtins, files: {} };
for (const file of input.files) {
  let text;
  try { text = fs.readFileSync(file, 'utf8'); } catch (e) { continue; }
  const src = scriptText(file, text);
  const info = ts.preProcessFile(src, true, true);
  const specs = new Set(info.importedFiles.map((f) => f.fileName));
  // re-exports and type-only imports are included by preProcessFile; also catch require.resolve and new URL(import.meta.url)
  const { options, cache } = optionsFor(file);
  const items = [];
  for (const spec of specs) {
    let target = null;
    try {
      const r = ts.resolveModuleName(spec, file, options, ts.sys, cache);
      if (r && r.resolvedModule) target = r.resolvedModule.resolvedFileName;
    } catch (e) { /* unresolved */ }
    if (target && ts.sys.realpath) {
      try { target = ts.sys.realpath(target); } catch (e) { /* keep */ }
    }
    items.push([spec, target]);
  }
  out.files[file] = items;
}
process.stdout.write(JSON.stringify(out));
