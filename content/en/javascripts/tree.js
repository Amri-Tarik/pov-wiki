/* Path of Valheiman DB: interactive passive tree.
 *
 * Reads the generated tree-data.json:
 *   nodes:    [id, x, y, sizeIndex, branchIndex, title, tooltipHtml, flags, iconPath, frameIndex]
 *   links:    [from, to] or [from, to, cx, cy]  (quadratic curve, control = midpoint + (cx, cy))
 *   sizes:    [{name, d}]   game node diameters
 *   branches: [{name, color}] game branch colours
 *   ui:       wiki strings
 *   iconBase: URL prefix for iconPath (icons can be turned off: then iconPath is "")
 *   frames:   frame kinds; iconBase + "frame/<kind>-<locked|allocated>.webp" (empty when icons are off)
 * Close up, a node is drawn like the game's tree window: dark backing, the painted icon cropped
 * to a circle (or a branch-coloured dot), then the painted frame at node size / 0.82. Frames are
 * silver, and gold for highlighted nodes, like allocated nodes in game.
 * Game coordinates are y-up (Unity UI); the canvas is y-down, so y is flipped.
 */
(function () {
  "use strict";

  var F_PAGE = 1, F_UNIMPL = 2, F_OPTIONS = 4;
  var S_SMALL = 0, S_TRAVEL = 1, S_NOTABLE = 2, S_KEYSTONE = 3, S_SOCKET = 4, S_MASTERY = 5, S_PORTAL = 7;
  var CELL = 120; // hit-test grid cell, world units
  var ICON_MIN_PX = 9; // draw icons and frames once a node's radius reaches this many screen pixels
  var FRAME_RING = 0.82; // UiKit.FrameRing: node box / frame size
  var INSET = { keystone: 0.06, normal: 0.02, mastery: 0.025 }; // icon inset in the node box

  function boot() {
    document.querySelectorAll(".pov-tree").forEach(function (root) {
      if (root.dataset.ready) return;
      root.dataset.ready = "1";
      fetch(root.dataset.tree)
        .then(function (r) { return r.json(); })
        .then(function (data) { new TreeView(root, data); });
    });
  }

  function TreeView(root, data) {
    this.root = root;
    this.data = data;
    this.base = root.dataset.nodeBase;
    this.build();
    this.prepare();
    this.bind();
    this.fit();
    this.focusHash();
  }

  TreeView.prototype.build = function () {
    var ui = this.data.ui;
    this.root.innerHTML =
      '<div class="pov-tree-bar">' +
      '<input type="search" class="pov-tree-search md-input" placeholder="' + ui.search + '">' +
      '<span class="pov-tree-count"></span>' +
      '<button type="button" class="pov-tree-reset md-button">' + ui.reset + "</button>" +
      "</div>" +
      // Inline layout: the canvas is taken out of the flow, so its size can never feed back into
      // the box it is measured from, whatever the stylesheet says.
      '<div class="pov-tree-wrap" style="position:relative;height:75vh;min-height:420px;overflow:hidden;touch-action:none">' +
      '<canvas style="position:absolute;left:0;top:0;display:block"></canvas>' +
      '<div class="pov-tree-tip" style="position:absolute" hidden></div></div>' +
      '<div class="pov-tree-hint">' + ui.hint + "</div>";
    this.wrap = this.root.querySelector(".pov-tree-wrap");
    this.canvas = this.root.querySelector("canvas");
    this.ctx = this.canvas.getContext("2d");
    this.tip = this.root.querySelector(".pov-tree-tip");
    this.search = this.root.querySelector(".pov-tree-search");
    this.count = this.root.querySelector(".pov-tree-count");
  };

  TreeView.prototype.prepare = function () {
    var d = this.data, nodes = [], byId = {}, grid = {};
    var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    d.nodes.forEach(function (n, i) {
      var node = {
        i: i, id: n[0], x: n[1], y: -n[2], size: n[3], branch: n[4], title: n[5], tip: n[6], flags: n[7],
        r: d.sizes[n[3]].d / 2, icon: n[8] ? d.iconBase + n[8] : null,
        frame: d.frames.length ? d.frames[n[9]] : null,
      };
      // Searchable: title and tooltip text. Jewel sockets have neither, so their type name
      // ("Jewel socket") is searchable too.
      node.text = [node.title, node.size === S_SOCKET ? d.sizes[node.size].name : "", node.tip.replace(/<[^>]+>/g, " ")]
        .join(" ").toLowerCase();
      nodes.push(node);
      byId[node.id] = node;
      minX = Math.min(minX, node.x); maxX = Math.max(maxX, node.x);
      minY = Math.min(minY, node.y); maxY = Math.max(maxY, node.y);
      var key = Math.floor(node.x / CELL) + "," + Math.floor(node.y / CELL);
      (grid[key] = grid[key] || []).push(node);
    });
    this.nodes = nodes;
    this.byId = byId;
    this.grid = grid;
    this.bounds = { minX: minX, minY: minY, maxX: maxX, maxY: maxY };
    this.links = d.links.map(function (l) {
      return { a: nodes[l[0]], b: nodes[l[1]], cx: l.length > 2 ? l[2] : null, cy: l.length > 2 ? -l[3] : null };
    });
    this.view = { s: 1, tx: 0, ty: 0 };
    this.matches = null;
    this.matchList = [];
    this.matchAt = -1;
    this.hover = null;
    this.pinned = null;
    this.images = {};
  };

  TreeView.prototype.image = function (url) {
    var self = this, img = this.images[url];
    if (!img) {
      img = this.images[url] = new Image();
      img.onload = function () { self.redraw(); };
      img.src = url;
    }
    return img.complete && img.naturalWidth ? img : null;
  };

  // ---- View -----------------------------------------------------------------------------------

  TreeView.prototype.resize = function () {
    var dpr = window.devicePixelRatio || 1, w = this.wrap.clientWidth, h = this.wrap.clientHeight;
    this.w = w;
    this.h = h;
    this.canvas.width = Math.round(w * dpr);
    this.canvas.height = Math.round(h * dpr);
    this.canvas.style.width = w + "px";
    this.canvas.style.height = h + "px";
    this.dpr = dpr;
    this.redraw();
  };

  TreeView.prototype.fit = function () {
    this.resize();
    var b = this.bounds, pad = 40;
    var s = Math.min((this.w - pad * 2) / (b.maxX - b.minX), (this.h - pad * 2) / (b.maxY - b.minY));
    this.view.s = s;
    this.view.tx = this.w / 2 - ((b.minX + b.maxX) / 2) * s;
    this.view.ty = this.h / 2 - ((b.minY + b.maxY) / 2) * s;
    this.redraw();
  };

  TreeView.prototype.centerOn = function (node, scale) {
    var s = Math.max(this.view.s, scale || 0.6);
    this.view.s = s;
    this.view.tx = this.w / 2 - node.x * s;
    this.view.ty = this.h / 2 - node.y * s;
    this.redraw();
  };

  TreeView.prototype.zoomAt = function (factor, sx, sy) {
    var v = this.view, s = Math.min(4, Math.max(this.minScale(), v.s * factor));
    v.tx = sx - ((sx - v.tx) * s) / v.s;
    v.ty = sy - ((sy - v.ty) * s) / v.s;
    v.s = s;
    this.redraw();
  };

  TreeView.prototype.minScale = function () {
    var b = this.bounds;
    return 0.5 * Math.min(this.w / (b.maxX - b.minX), this.h / (b.maxY - b.minY));
  };

  TreeView.prototype.toWorld = function (sx, sy) {
    return { x: (sx - this.view.tx) / this.view.s, y: (sy - this.view.ty) / this.view.s };
  };

  TreeView.prototype.hit = function (sx, sy) {
    var p = this.toWorld(sx, sy), gx = Math.floor(p.x / CELL), gy = Math.floor(p.y / CELL), best = null, bestD = Infinity;
    var slack = 6 / this.view.s; // a few screen pixels of tolerance
    for (var dx = -1; dx <= 1; dx++) {
      for (var dy = -1; dy <= 1; dy++) {
        var cell = this.grid[gx + dx + "," + (gy + dy)];
        if (!cell) continue;
        for (var k = 0; k < cell.length; k++) {
          var n = cell[k], d = Math.hypot(n.x - p.x, n.y - p.y);
          if (d <= Math.max(n.r, 3 / this.view.s) + slack && d < bestD) { best = n; bestD = d; }
        }
      }
    }
    return best;
  };

  // ---- Drawing --------------------------------------------------------------------------------

  TreeView.prototype.redraw = function () {
    var self = this;
    if (this.pending) return;
    this.pending = true;
    requestAnimationFrame(function () { self.pending = false; self.draw(); });
  };

  TreeView.prototype.draw = function () {
    var c = this.ctx, v = this.view, s = v.s, css = getComputedStyle(this.root);
    var bg = css.getPropertyValue("--md-default-bg-color").trim() || "#1e1e1e";
    var fg = css.getPropertyValue("--md-default-fg-color").trim() || "#ddd";
    var accent = css.getPropertyValue("--md-accent-fg-color").trim() || "#fa0";
    var matches = this.matches;

    c.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    c.fillStyle = bg;
    c.fillRect(0, 0, this.w, this.h);
    c.save();
    c.translate(v.tx, v.ty);
    c.scale(s, s);

    // Visible world rectangle, for culling.
    var a = this.toWorld(0, 0), b = this.toWorld(this.w, this.h), m = 80;
    var vx0 = a.x - m, vy0 = a.y - m, vx1 = b.x + m, vy1 = b.y + m;
    function visible(n) { return n.x > vx0 && n.x < vx1 && n.y > vy0 && n.y < vy1; }

    // Links: everything dim, then links between matched nodes bright.
    c.lineCap = "round";
    c.lineWidth = Math.max(5, 1.2 / s);
    c.strokeStyle = fg;
    c.globalAlpha = matches ? 0.08 : 0.28;
    this.strokeLinks(c, function (l) { return visible(l.a) || visible(l.b); });
    if (matches) {
      c.globalAlpha = 0.6;
      this.strokeLinks(c, function (l) { return matches[l.a.i] && matches[l.b.i]; });
    }

    // Nodes.
    var branches = this.data.branches, lit = {};
    [this.hover, this.pinned].forEach(function (h) { if (h) lit[h.i] = true; });
    for (var i = 0; i < this.nodes.length; i++) {
      var n = this.nodes[i];
      if (!visible(n)) continue;
      var r = Math.max(n.r, 1.6 / s), unimpl = n.flags & F_UNIMPL;
      c.globalAlpha = matches && !matches[n.i] ? 0.15 : unimpl ? 0.45 : 1;
      if (n.frame && r * s >= ICON_MIN_PX) {
        this.drawFramed(c, n, r, unimpl, (matches && matches[n.i]) || lit[n.i]);
        continue;
      }
      c.fillStyle = unimpl ? "#808080" : branches[n.branch].color;
      c.beginPath();
      this.shape(c, n, r);
      c.fill();
      if (n.size === S_KEYSTONE || n.size === S_NOTABLE || n.size === S_PORTAL || (n.flags & F_OPTIONS)) {
        c.lineWidth = Math.max(n.size === S_KEYSTONE ? 7 : 4, 1 / s);
        c.strokeStyle = n.flags & F_OPTIONS ? fg : bg;
        c.stroke();
      }
      if (unimpl) {
        c.setLineDash([6, 6]);
        c.lineWidth = Math.max(3, 1 / s);
        c.strokeStyle = fg;
        c.stroke();
        c.setLineDash([]);
      }
    }

    // Highlights: matches, hover, pinned.
    c.globalAlpha = 1;
    c.lineWidth = Math.max(5, 2.5 / s);
    if (matches) {
      c.strokeStyle = accent;
      for (var j = 0; j < this.matchList.length; j++) {
        var mn = this.matchList[j];
        if (!visible(mn)) continue;
        c.beginPath();
        c.arc(mn.x, mn.y, Math.max(mn.r, 2 / s) + Math.max(8, 3 / s), 0, Math.PI * 2);
        c.stroke();
      }
    }
    [this.hover, this.pinned].forEach(function (h) {
      if (!h) return;
      c.strokeStyle = fg;
      c.beginPath();
      c.arc(h.x, h.y, Math.max(h.r, 2 / s) + Math.max(10, 4 / s), 0, Math.PI * 2);
      c.stroke();
    });
    c.restore();

    // Labels in screen space, so they stay crisp: keystones first, notables when zoomed in.
    c.font = "600 12px " + (css.getPropertyValue("--md-text-font-family").trim() || "sans-serif");
    c.textAlign = "center";
    c.textBaseline = "top";
    for (var k = 0; k < this.nodes.length; k++) {
      var ln = this.nodes[k];
      if (!ln.title || (ln.flags & F_UNIMPL)) continue;
      if (!(ln.size === S_KEYSTONE ? s > 0.12 : ln.size === S_NOTABLE ? s > 0.45 : false)) continue;
      if (matches && !matches[ln.i]) continue;
      var px = ln.x * s + v.tx, py = (ln.y + ln.r) * s + v.ty + 4;
      if (px < -100 || px > this.w + 100 || py < -20 || py > this.h + 20) continue;
      c.globalAlpha = 1;
      c.lineWidth = 3;
      c.strokeStyle = bg;
      c.strokeText(ln.title, px, py);
      c.fillStyle = fg;
      c.fillText(ln.title, px, py);
    }
  };

  TreeView.prototype.drawFramed = function (c, n, r, unimpl, gold) {
    var base = this.data.iconBase, frame = this.image(base + "frame/" + n.frame + "-" + (gold ? "allocated" : "locked") + ".webp");
    var icon = n.icon ? this.image(n.icon) : null;
    // Backing.
    c.fillStyle = "#16130f";
    c.beginPath();
    c.arc(n.x, n.y, r, 0, Math.PI * 2);
    c.fill();
    if (icon) {
      var ir = r * (1 - 2 * (INSET[n.frame] || 0));
      c.save();
      c.beginPath();
      c.arc(n.x, n.y, ir, 0, Math.PI * 2);
      c.clip();
      if (unimpl) c.filter = "grayscale(1)";
      c.drawImage(icon, n.x - ir, n.y - ir, ir * 2, ir * 2);
      c.restore();
    } else {
      // No art: a dot in the branch colour, like the game's small passives.
      c.fillStyle = unimpl ? "#808080" : this.data.branches[n.branch].color;
      c.beginPath();
      c.arc(n.x, n.y, r * 0.36, 0, Math.PI * 2);
      c.fill();
    }
    if (frame) {
      var fr = r / FRAME_RING;
      c.drawImage(frame, n.x - fr, n.y - fr, fr * 2, fr * 2);
    }
  };

  TreeView.prototype.strokeLinks = function (c, keep) {
    c.beginPath();
    for (var i = 0; i < this.links.length; i++) {
      var l = this.links[i];
      if (!keep(l)) continue;
      c.moveTo(l.a.x, l.a.y);
      if (l.cx === null) c.lineTo(l.b.x, l.b.y);
      else c.quadraticCurveTo((l.a.x + l.b.x) / 2 + l.cx, (l.a.y + l.b.y) / 2 + l.cy, l.b.x, l.b.y);
    }
    c.stroke();
  };

  TreeView.prototype.shape = function (c, n, r) {
    if (n.size === S_SOCKET || n.size === S_MASTERY) {
      c.moveTo(n.x, n.y - r); c.lineTo(n.x + r, n.y); c.lineTo(n.x, n.y + r); c.lineTo(n.x - r, n.y); c.closePath();
    } else {
      c.arc(n.x, n.y, r, 0, Math.PI * 2);
    }
  };

  // ---- Tooltip --------------------------------------------------------------------------------

  TreeView.prototype.showTip = function (n, sx, sy) {
    if (!n) { this.tip.hidden = true; return; }
    var d = this.data;
    this.tip.innerHTML =
      (n.icon ? '<img class="pov-tt-icon" src="' + n.icon + '" width="40" height="40" alt="" ' +
        'style="float:left;width:40px;height:40px;margin:0 8px 4px 0;border-radius:50%">' : "") +
      '<div class="pov-tt-title">' + (n.title || "—") + "</div>" +
      '<div class="pov-tt-meta">' + d.sizes[n.size].name + " · " + d.branches[n.branch].name + "</div>" +
      n.tip;
    this.tip.hidden = false;
    var tw = this.tip.offsetWidth, th = this.tip.offsetHeight;
    var x = sx + 16, y = sy + 16;
    if (x + tw > this.w - 8) x = Math.max(8, sx - tw - 16);
    if (y + th > this.h - 8) y = Math.max(8, this.h - th - 8);
    this.tip.style.left = x + "px";
    this.tip.style.top = y + "px";
  };

  // ---- Input ----------------------------------------------------------------------------------

  TreeView.prototype.bind = function () {
    var self = this, cv = this.canvas, pointers = {}, drag = null, pinch = null;

    new ResizeObserver(function () { self.resize(); }).observe(this.wrap);

    function pos(e) {
      var rect = cv.getBoundingClientRect();
      return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    }

    cv.addEventListener("pointerdown", function (e) {
      cv.setPointerCapture(e.pointerId);
      pointers[e.pointerId] = pos(e);
      var ids = Object.keys(pointers);
      if (ids.length === 1) {
        drag = { start: pos(e), last: pos(e), moved: false };
      } else if (ids.length === 2) {
        var p = pointers[ids[0]], q = pointers[ids[1]];
        pinch = { dist: Math.hypot(p.x - q.x, p.y - q.y) };
        drag = null;
      }
    });

    cv.addEventListener("pointermove", function (e) {
      var p = pos(e);
      if (pointers[e.pointerId]) pointers[e.pointerId] = p;
      var ids = Object.keys(pointers);
      if (pinch && ids.length === 2) {
        var a = pointers[ids[0]], b = pointers[ids[1]], dist = Math.hypot(a.x - b.x, a.y - b.y);
        self.zoomAt(dist / pinch.dist, (a.x + b.x) / 2, (a.y + b.y) / 2);
        pinch.dist = dist;
        return;
      }
      if (drag) {
        if (Math.hypot(p.x - drag.start.x, p.y - drag.start.y) > 4) drag.moved = true;
        if (drag.moved) {
          self.view.tx += p.x - drag.last.x;
          self.view.ty += p.y - drag.last.y;
          drag.last = p;
          self.tip.hidden = true;
          self.redraw();
          return;
        }
      }
      if (e.pointerType === "mouse" && !self.pinned) {
        var n = self.hit(p.x, p.y);
        cv.style.cursor = n ? "pointer" : "grab";
        if (n !== self.hover) { self.hover = n; self.redraw(); }
        self.showTip(n, p.x, p.y);
      }
    });

    function up(e) {
      var p = pos(e), wasDrag = drag;
      delete pointers[e.pointerId];
      if (Object.keys(pointers).length < 2) pinch = null;
      drag = null;
      if (e.type !== "pointerup" || !wasDrag || wasDrag.moved) return;
      var n = self.hit(p.x, p.y);
      if (n && (n.flags & F_PAGE) && (self.pinned === n || e.pointerType === "mouse")) {
        window.location.href = self.base + n.id + "/";
        return;
      }
      // Touch, or nodes without a page: tap pins the tooltip (tap again to open the page).
      self.pinned = n;
      self.hover = n;
      self.showTip(n, p.x, p.y);
      self.redraw();
    }
    cv.addEventListener("pointerup", up);
    cv.addEventListener("pointercancel", up);
    cv.addEventListener("pointerleave", function () {
      if (!self.pinned) { self.hover = null; self.tip.hidden = true; self.redraw(); }
    });

    cv.addEventListener("wheel", function (e) {
      e.preventDefault();
      var p = pos(e);
      self.zoomAt(Math.exp(-e.deltaY * 0.0015), p.x, p.y);
      if (self.pinned) { self.pinned = null; self.tip.hidden = true; }
    }, { passive: false });

    var timer = null;
    this.search.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () { self.runSearch(self.search.value); }, 150);
    });
    this.search.addEventListener("keydown", function (e) {
      if (e.key !== "Enter" || !self.matchList.length) return;
      e.preventDefault();
      self.matchAt = (self.matchAt + 1) % self.matchList.length;
      var n = self.matchList[self.matchAt];
      self.centerOn(n, 0.7);
      self.pinned = n;
      self.hover = n;
      self.showTip(n, self.w / 2, self.h / 2);
      self.count.textContent = self.data.ui.matches.replace("{count}", self.matchList.length) + " (" + (self.matchAt + 1) + ")";
    });
    this.root.querySelector(".pov-tree-reset").addEventListener("click", function () {
      self.search.value = "";
      self.runSearch("");
      self.pinned = null;
      self.hover = null;
      self.tip.hidden = true;
      self.fit();
    });
    window.addEventListener("hashchange", function () { self.focusHash(); });
  };

  TreeView.prototype.runSearch = function (q) {
    var terms = q.toLowerCase().split(/\s+/).filter(Boolean);
    this.matchAt = -1;
    if (!terms.length) {
      this.matches = null;
      this.matchList = [];
      this.count.textContent = "";
      this.redraw();
      return;
    }
    var matches = {}, list = [];
    this.nodes.forEach(function (n) {
      for (var i = 0; i < terms.length; i++) if (n.text.indexOf(terms[i]) < 0) return;
      matches[n.i] = true;
      list.push(n);
    });
    // Bigger nodes first when cycling through matches.
    list.sort(function (a, b) { return b.r - a.r; });
    this.matches = matches;
    this.matchList = list;
    this.count.textContent = this.data.ui.matches.replace("{count}", list.length);
    this.redraw();
  };

  TreeView.prototype.focusHash = function () {
    var id = decodeURIComponent(window.location.hash.slice(1)), n = id && this.byId[id];
    if (!n) return;
    this.centerOn(n, 0.8);
    this.pinned = n;
    this.hover = n;
    this.showTip(n, this.w / 2, this.h / 2);
  };

  // Material/Zensical instant navigation swaps pages without a reload; document$ fires each time.
  if (window.document$) window.document$.subscribe(boot);
  else document.addEventListener("DOMContentLoaded", boot);
})();
