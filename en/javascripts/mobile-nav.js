/* Mobile navigation: the sidebars follow swipes, and are easier to find.

   Below the desktop width the theme hides the left menu in a drawer (☰) and, on phones, the
   "On this page" list in a pop-up (bottom right). Here:
   - swiping right opens the drawer, which follows the finger; swiping left closes it;
   - swiping left, with the drawer shut, opens "On this page"; swiping right closes it;
   - a tab on the left edge and labels on both buttons say where navigation is;
   - the first visit on a phone shows the drawer peeking out once, with a short hint.
   A swipe that starts in something that scrolls sideways (a wide table) scrolls it first, and
   the tree viewer keeps its own gestures. Labels come from the page (meta "pov-ui"), in its
   language. */
(function () {
  var DRAWER = "(max-width: 76.234375em)", POPUP = "(max-width: 59.984375em)";
  var SEEN = "pov-nav-hint-seen";
  var LOCK = 10, COMMIT = 0.4, FLICK = 0.4; // px before a direction is chosen; share of the way; px/ms

  function matches(q) { return window.matchMedia(q).matches; }
  function $(s) { return document.querySelector(s); }
  function labels() { var m = $('meta[name="pov-ui"]'); return m ? m.dataset : {}; }
  function rem() { return parseFloat(getComputedStyle(document.documentElement).fontSize) || 20; }
  function drawerInput() { return document.getElementById("__drawer"); }
  function tocInput() { return document.getElementById("__toc"); }
  function tocButton() {
    var b = $(".md-sidebar--secondary .md-sidebar-button");
    return b && b.offsetParent !== null ? b : null; // shown only on phones, when the page has headings
  }
  // Toggle a theme checkbox by clicking it, so the theme sees the change like a tap.
  function setInput(input, on) { if (input && input.checked !== on) input.click(); }

  function seen() {
    try { localStorage.setItem(SEEN, "1"); } catch (e) { /* private mode */ }
    document.body.classList.remove("pov-hinting");
    var hint = $(".pov-nav-hint");
    if (hint) hint.remove();
  }

  // Something between the touch and the page that can still scroll that way takes the swipe.
  function scrollsSideways(el, dx) {
    for (; el && el !== document.body; el = el.parentElement) {
      var o = getComputedStyle(el).overflowX;
      if ((o === "auto" || o === "scroll") && el.scrollWidth > el.clientWidth + 1) {
        if (dx > 0 ? el.scrollLeft > 0 : el.scrollLeft + el.clientWidth < el.scrollWidth - 1) return true;
      }
    }
    return false;
  }

  // ---- Swipes -----------------------------------------------------------------------------
  var g = null; // the touch being followed

  function follow(p) { // the drawer and its overlay at p (0 shut, 1 open)
    var side = $(".md-sidebar--primary"), shade = $(".md-overlay");
    g.width = g.width || 12.5 * rem();
    if (side) { side.style.transition = "none"; side.style.transform = "translateX(" + p * g.width + "px)"; }
    if (shade) {
      shade.style.transition = "none"; shade.style.width = "100%"; shade.style.height = "100%";
      shade.style.opacity = String(p);
    }
  }

  function release() { // hand the drawer back to the theme's own styles and transitions
    var side = $(".md-sidebar--primary"), shade = $(".md-overlay");
    [side, shade].forEach(function (el) { if (el) el.style.transition = ""; });
    requestAnimationFrame(function () {
      if (side) side.style.transform = "";
      if (shade) { shade.style.width = shade.style.height = shade.style.opacity = ""; }
    });
  }

  document.addEventListener("touchstart", function (e) {
    g = null;
    if (e.touches.length !== 1 || !matches(DRAWER)) return;
    var t = e.target;
    if (t.closest && t.closest(".pov-tree-wrap, input, textarea, select, [contenteditable], .md-search")) return;
    if (document.getElementById("__search") && document.getElementById("__search").checked) return;
    var p = e.touches[0];
    g = { x: p.clientX, y: p.clientY, t: Date.now(), target: t, action: null, dx: 0 };
  }, { passive: true });

  document.addEventListener("touchmove", function (e) {
    if (!g || g.action === "none") return;
    var p = e.touches[0], dx = p.clientX - g.x, dy = p.clientY - g.y;
    g.dx = dx;
    if (!g.action) {
      if (Math.abs(dx) < LOCK && Math.abs(dy) < LOCK) return;
      var open = drawerInput() && drawerInput().checked, toc = tocInput() && tocInput().checked;
      if (Math.abs(dx) < 1.2 * Math.abs(dy)) g.action = "none"; // scrolling the page
      else if (open) g.action = dx < 0 ? "close" : "none";
      else if (toc) g.action = dx > 0 ? "toc-close" : "none";
      else if (scrollsSideways(g.target, dx)) g.action = "none";
      else if (dx > 0) g.action = "open";
      else g.action = matches(POPUP) && tocButton() ? "toc-open" : "none";
      if (g.action === "none") return;
    }
    if (g.action === "open" || g.action === "close") {
      e.preventDefault(); // the drawer moves, not the page
      var w = g.width || 12.5 * rem();
      follow(Math.max(0, Math.min(1, g.action === "open" ? dx / w : 1 + dx / w)));
    }
  }, { passive: false });

  document.addEventListener("touchend", function () {
    if (!g || !g.action || g.action === "none") { g = null; return; }
    var w = g.width || 12.5 * rem(), v = g.dx / Math.max(1, Date.now() - g.t);
    if (g.action === "open" || g.action === "close") {
      var p = g.action === "open" ? g.dx / w : 1 + g.dx / w;
      var on = g.action === "open" ? (p > COMMIT || v > FLICK) : !(p < 1 - COMMIT || v < -FLICK);
      release();
      setInput(drawerInput(), on);
      if (on) seen();
    } else if (Math.abs(g.dx) > 3 * LOCK) {
      setInput(tocInput(), g.action === "toc-open");
    }
    g = null;
  });

  document.addEventListener("touchcancel", function () { if (g && (g.action === "open" || g.action === "close")) release(); g = null; });

  // ---- Finding the navigation -----------------------------------------------------------------
  function decorate() {
    var ui = labels();
    var menu = $('.md-header__button[for="__drawer"]');
    if (menu && ui.menu && !menu.querySelector(".pov-menu-label")) {
      var span = document.createElement("span");
      span.className = "pov-menu-label";
      span.textContent = ui.menu;
      menu.appendChild(span);
      menu.classList.add("pov-menu-button");
    }
    var toc = $(".md-sidebar--secondary .md-sidebar-button");
    if (toc && ui.toc && !toc.querySelector(".pov-toc-label")) {
      var label = document.createElement("span");
      label.className = "pov-toc-label";
      label.textContent = ui.toc;
      toc.appendChild(label);
    }
    if (!document.querySelector(".pov-edge-tab")) {
      var tab = document.createElement("label");
      tab.className = "pov-edge-tab";
      tab.htmlFor = "__drawer";
      tab.setAttribute("aria-label", ui.open || ui.menu || "Menu");
      tab.addEventListener("click", seen);
      var drawer = drawerInput();
      if (drawer) drawer.insertAdjacentElement("afterend", tab); // a sibling, so CSS can hide it while open
    }
  }

  function hintOnce() {
    var shown = false;
    try { shown = !!localStorage.getItem(SEEN); } catch (e) { shown = true; }
    if (shown || !matches(DRAWER) || matches("(prefers-reduced-motion: reduce)")) return;
    setTimeout(function () {
      if (drawerInput() && drawerInput().checked) return seen();
      var ui = labels();
      document.body.classList.add("pov-hinting");
      if (ui.hint && !$(".pov-nav-hint")) {
        var hint = document.createElement("div");
        hint.className = "pov-nav-hint";
        hint.textContent = ui.hint;
        hint.addEventListener("click", seen);
        document.body.appendChild(hint);
      }
      setTimeout(seen, 6000);
    }, 1200);
  }

  function boot() { decorate(); }
  // Instant navigation swaps pages without a reload; document$ fires each time.
  function ready(f) { if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", f); else f(); }
  if (window.document$) window.document$.subscribe(boot);
  else ready(boot);
  ready(hintOnce);
  document.addEventListener("change", function (e) { if (e.target === drawerInput() && e.target.checked) seen(); });
})();
