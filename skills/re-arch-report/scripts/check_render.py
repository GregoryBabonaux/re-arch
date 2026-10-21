#!/usr/bin/env python3
"""
re-arch-report / check_render.py

Opens the report in headless Chromium (Playwright) at phone and desktop
widths, visits every tab, and fails if the page scrolls horizontally or an
element overflows the viewport. Saves screenshots next to the report so the
rendering can be looked at, not assumed.

Usage: python3 check_render.py <repo>/.re-arch/report.html [--widths 390,1280]
Requires: pip install playwright && python -m playwright install chromium
"""
import argparse
import os
import sys

CHECK_JS = r"""
() => {
  const vw = document.documentElement.clientWidth;
  const doc = document.scrollingElement.scrollWidth;
  const offenders = [];
  const skip = el => el.closest('nav.tabs');
  for (const el of document.querySelectorAll('section.panel.on *, header.top *')) {
    if (skip(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    if (r.right > vw + 1 || r.left < -1) {
      offenders.push((el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ').join('.') : '')) + ' right=' + Math.round(r.right));
      if (offenders.length > 8) break;
    }
  }
  return {vw, doc, offenders};
}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("--widths", default="390,1280")
    args = ap.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed: run `pip install playwright && python -m playwright install chromium`, "
              "or open the report in a browser with device emulation at 390px and check each tab by eye.")
        sys.exit(3)
    path = os.path.abspath(args.report)
    shots = os.path.join(os.path.dirname(path), "screenshots")
    os.makedirs(shots, exist_ok=True)
    problems = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for w in [int(x) for x in args.widths.split(",")]:
            page = browser.new_page(viewport={"width": w, "height": 900}, device_scale_factor=2 if w < 600 else 1)
            page.goto("file://" + path)
            tabs = page.eval_on_selector_all("nav.tabs a", "els => els.map(e => e.getAttribute('href'))")
            for href in tabs:
                page.evaluate("h => { location.hash = h; }", href)
                page.wait_for_timeout(150)
                page.evaluate("() => window.scrollTo(0, 0)")
                res = page.evaluate(CHECK_JS)
                name = href.strip("#")
                page.screenshot(path=os.path.join(shots, f"{w}-{name}.png"), full_page=True)
                # first screen of the tab, readable at a glance (full-page shots get very tall)
                page.screenshot(path=os.path.join(shots, f"{w}-{name}-top.png"), full_page=False)
                for fig_i, fig in enumerate(page.query_selector_all("section.panel.on figure.mapfig")):
                    if fig.is_visible():
                        fig.screenshot(path=os.path.join(shots, f"{w}-{name}-figure{fig_i + 1}.png"))
                ok = res["doc"] <= res["vw"] + 1 and not res["offenders"]
                if not ok:
                    problems += 1
                print(f"{'OK  ' if ok else 'FAIL'} {w}px #{name}: page width {res['doc']} / viewport {res['vw']}"
                      + ("" if ok else f" overflowing: {'; '.join(res['offenders'])}"))
            page.close()
        browser.close()
    print(f"screenshots in {shots}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
