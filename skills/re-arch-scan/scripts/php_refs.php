<?php
/*
 * php_refs.php: every class-like name referenced by each PHP file, resolved
 * with PHP's own name resolution rules (namespace, use, use group, aliases,
 * fully qualified and qualified names, ::class). Uses the PHP tokenizer only:
 * nothing from the repository is executed or included.
 *
 * stdin:  ["/abs/a.php", ...]
 * stdout: {"/abs/a.php": [["App\\Models\\User", true], ...]}   (name, came from a use statement)
 * Works on PHP 7.x and 8.x.
 */

foreach (['T_NAME_QUALIFIED', 'T_NAME_FULLY_QUALIFIED', 'T_NAME_RELATIVE', 'T_ATTRIBUTE', 'T_ENUM', 'T_READONLY', 'T_NULLSAFE_OBJECT_OPERATOR', 'T_MATCH'] as $c) {
    if (!defined($c)) { define($c, -1000 - strlen($c)); }
}

$files = json_decode(stream_get_contents(STDIN), true) ?: [];
$skipBefore = [T_OBJECT_OPERATOR, T_NULLSAFE_OBJECT_OPERATOR, T_FUNCTION, T_CONST, T_GOTO, T_DOUBLE_COLON];
$builtinTypes = ['self','static','parent','int','float','string','bool','array','callable','iterable','object','mixed','void','null','never','false','true','resource','integer','boolean','double'];
$out = [];

foreach ($files as $file) {
    $code = @file_get_contents($file);
    if ($code === false) { continue; }
    $tokens = @token_get_all($code);
    $n = count($tokens);
    $ns = '';
    $uses = [];      // alias(lower) => FQCN
    $refs = [];      // FQCN => fromUse
    $braceDepth = 0;
    $classBodyDepth = -1;  // trait `use` inside classes is a class reference, not an import

    // merge PHP 7 style names (T_STRING T_NS_SEPARATOR T_STRING...) into single name tokens
    $toks = [];
    for ($i = 0; $i < $n; $i++) {
        $t = $tokens[$i];
        if (is_array($t) && in_array($t[0], [T_STRING, T_NS_SEPARATOR, T_NAMESPACE], true) && $t[0] !== T_NAMESPACE) {
            $name = $t[1];
            $j = $i + 1;
            while ($j < $n && is_array($tokens[$j]) && in_array($tokens[$j][0], [T_STRING, T_NS_SEPARATOR], true)) {
                $name .= $tokens[$j][1];
                $j++;
            }
            if ($j > $i + 1 || strpos($name, '\\') !== false) {
                $type = $name[0] === '\\' ? T_NAME_FULLY_QUALIFIED : (strpos($name, '\\') !== false ? T_NAME_QUALIFIED : T_STRING);
                $toks[] = [$type, $name];
                $i = $j - 1;
                continue;
            }
        }
        if (is_array($t) && in_array($t[0], [T_WHITESPACE, T_COMMENT, T_DOC_COMMENT], true)) { continue; }
        $toks[] = $t;
    }
    $m = count($toks);
    $id = function ($k) use ($toks) { return isset($toks[$k]) ? (is_array($toks[$k]) ? $toks[$k][0] : $toks[$k]) : null; };
    $txt = function ($k) use ($toks) { return isset($toks[$k]) ? (is_array($toks[$k]) ? $toks[$k][1] : $toks[$k]) : ''; };

    $resolve = function ($name) use (&$ns, &$uses) {
        if ($name === '' ) { return null; }
        if ($name[0] === '\\') { return ltrim($name, '\\'); }
        if (stripos($name, 'namespace\\') === 0) { return trim($ns . '\\' . substr($name, 10), '\\'); }
        $parts = explode('\\', $name);
        $first = strtolower($parts[0]);
        if (isset($uses[$first])) {
            $parts[0] = $uses[$first];
            return implode('\\', $parts);
        }
        return trim($ns . '\\' . $name, '\\');
    };

    for ($k = 0; $k < $m; $k++) {
        $tid = $id($k);
        if ($tid === '{' || $tid === T_CURLY_OPEN || $tid === T_DOLLAR_OPEN_CURLY_BRACES) { $braceDepth++; continue; }
        if ($tid === '}') { $braceDepth--; if ($braceDepth < $classBodyDepth) { $classBodyDepth = -1; } continue; }
        if ($tid === T_NAMESPACE && in_array($id($k + 1), [T_STRING, T_NAME_QUALIFIED], true)) {
            $ns = trim($txt($k + 1), '\\');
            $uses = [];
            $k++;
            continue;
        }
        if (in_array($tid, [T_CLASS, T_INTERFACE, T_TRAIT, T_ENUM], true) && $id($k - 1) !== T_DOUBLE_COLON) {
            // the body starts at the next "{"
            for ($q = $k; $q < $m; $q++) { if ($id($q) === '{') { $classBodyDepth = $braceDepth + 1; break; } }
        }
        if ($tid === T_USE && $braceDepth === 0) {
            // import statement: use A\B [as C], use A\{B, C as D}; skip function/const imports
            $k++;
            if (in_array(strtolower($txt($k)), ['function', 'const'], true)) {
                while ($k < $m && $id($k) !== ';') { $k++; }
                continue;
            }
            $prefix = '';
            $stmt = [];
            while ($k < $m && $id($k) !== ';') { $stmt[] = $toks[$k]; $k++; }
            $s = '';
            foreach ($stmt as $st) { $s .= is_array($st) ? (in_array($st[0], [T_AS], true) ? ' as ' : $st[1]) : $st; }
            if (preg_match('/^(.*?)\\\\?\{(.*)\}$/s', $s, $g)) {
                $prefix = trim($g[1], '\\') . '\\';
                $items = explode(',', $g[2]);
            } else {
                $items = explode(',', $s);
            }
            foreach ($items as $it) {
                $it = trim($it);
                if ($it === '') { continue; }
                $alias = null;
                if (preg_match('/^(.+?)\s+as\s+(\w+)$/i', $it, $a)) { $it = trim($a[1]); $alias = $a[2]; }
                $fq = ltrim($prefix . ltrim($it, '\\'), '\\');
                $parts = explode('\\', $fq);
                $uses[strtolower($alias ?: end($parts))] = $fq;
                $refs[$fq] = true;
            }
            continue;
        }
        if ($tid === T_USE && $classBodyDepth > 0 && $braceDepth === $classBodyDepth) {
            // trait use inside a class body
            $k++;
            while ($k < $m && !in_array($id($k), [';', '{'], true)) {
                if (in_array($id($k), [T_STRING, T_NAME_QUALIFIED, T_NAME_FULLY_QUALIFIED], true)) {
                    $r = $resolve($txt($k));
                    if ($r) { $refs[$r] = $refs[$r] ?? false; }
                }
                $k++;
            }
            if ($id($k) === '{') { $braceDepth++; }
            continue;
        }
        if (in_array($tid, [T_NAME_QUALIFIED, T_NAME_FULLY_QUALIFIED, T_NAME_RELATIVE], true)) {
            $prev = $id($k - 1);
            $next = $id($k + 1);
            if ($prev === T_NAMESPACE) { continue; }
            if ($next === '(' && !in_array($prev, [T_NEW], true)) {
                continue; // namespaced function call
            }
            $r = $resolve($txt($k));
            if ($r) { $refs[$r] = $refs[$r] ?? false; }
            continue;
        }
        if ($tid === T_STRING) {
            $prev = $id($k - 1);
            $next = $id($k + 1);
            $word = $txt($k);
            if (in_array($prev, $skipBefore, true)) { continue; }
            if (in_array(strtolower($word), $builtinTypes, true)) { continue; }
            if (in_array($prev, [T_CLASS, T_INTERFACE, T_TRAIT, T_ENUM], true)) { continue; } // declaration
            $classCtx = in_array($prev, [T_NEW, T_EXTENDS, T_IMPLEMENTS, T_INSTANCEOF, T_CATCH, '|', T_ATTRIBUTE], true)
                || $next === T_DOUBLE_COLON
                || ($prev === ',' && $next !== '(' && ctype_upper($word[0]))
                || ($next === T_VARIABLE)           // typed parameter or property
                || ($next === T_ELLIPSIS)
                || ($prev === ':' && ctype_upper($word[0]))  // return type
                || ($prev === '?' && ctype_upper($word[0]));
            if ($classCtx && $next !== '(' || ($prev === T_NEW)) {
                $r = $resolve($word);
                if ($r) { $refs[$r] = $refs[$r] ?? false; }
            }
        }
    }
    $list = [];
    foreach ($refs as $name => $fromUse) { $list[] = [$name, $fromUse]; }
    $out[$file] = $list;
}
echo json_encode($out ?: new stdClass());
