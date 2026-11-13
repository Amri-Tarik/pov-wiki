/* Ascension calculator (tools/ascension): what each boss essence makes of an item.

   The page holds an empty #pov-ascension; its data file (written by the build: povwiki.ascension
   calculator_data) has the reference medians and curve Valheim's items give, the essences, the
   item bases and the labels, in the page's language. compute() is the mod's ItemAscension.Compute:
   an item of a class (weapon kind and hands, kind of shield, or summoning staff) from a biome,
   raised to the essence's biome. Picking a base fills the form; every field can be changed, so
   an item from another mod can be typed in. */
(function () {
  var COMBAT = ["m_damage", "m_blunt", "m_slash", "m_pierce", "m_fire", "m_frost", "m_lightning", "m_poison", "m_spirit"];
  var DMG = 0, DMG_L = 1, DUR = 2, DUR_L = 3, BLOCK = 4, BLOCK_L = 5, DEFL = 6, DEFL_L = 7; // a reference's numbers

  function combat(d) { var s = 0; COMBAT.forEach(function (k) { s += d[k] || 0; }); return s; }
  function scale(d, k) {
    var o = {};
    Object.keys(d).forEach(function (key) { o[key] = COMBAT.indexOf(key) >= 0 ? d[key] * k : d[key]; });
    return o;
  }
  function curveOnly(cls) { return cls.indexOf("ElementalMagic/") === 0 || cls.indexOf("Scepters/") === 0; }

  function Refs(data) { this.cells = data.cells; this.curve = data.curve; }
  Refs.prototype.measured = function (cls) { return this.cells.some(function (c) { return cls in c; }); };
  Refs.prototype.effective = function (cls, hands) {
    if (this.measured(cls)) return cls;
    if (hands === "shield") return "shield:*";
    return this.measured("*/" + hands) ? "*/" + hands : "*";
  };
  Refs.prototype.value = function (cls, bi, k) { // ItemAscension.Value
    var cells = this.cells, curve = this.curve, i, j, v;
    if (cls in cells[bi]) return cells[bi][cls][k];
    for (i = bi - 1; i >= 0; i--) if (cls in cells[i]) {
      v = cells[i][cls][k];
      for (j = i + 1; j <= bi; j++) v *= curve[k][j];
      return v;
    }
    for (i = bi + 1; i < cells.length; i++) if (cls in cells[i]) {
      v = cells[i][cls][k];
      for (j = i; j > bi; j--) v /= Math.max(0.01, curve[k][j]);
      return v;
    }
    return 0;
  };
  Refs.prototype.ratio = function (k, src, dst) {
    var r = 1;
    for (var i = src + 1; i <= dst; i++) r *= this.curve[k][i];
    return r;
  };

  // ItemAscension.Compute, with the stats an upgraded item keeps (5.3.1).
  function compute(R, it, dst) {
    var cls = it.cls, hands = it.hands, shield = hands === "shield", eff = R.effective(cls, hands);
    var o = { d: it.d, dl: it.dl, dur: it.dur, durL: it.durL, block: it.block, blockL: it.blockL, defl: it.defl, deflL: it.deflL,
              curve: false };
    var unmeasured = !R.measured(eff), r;
    if (cls !== "summon") {
      if (!shield && (curveOnly(cls) || unmeasured)) {
        o.curve = true;
        if ((r = R.ratio(DMG, it.src, dst)) > 1) { o.d = scale(o.d, r); o.dl = scale(o.dl, r); }
      } else if (!shield) {
        var own = combat(it.d), want = R.value(eff, dst, DMG);
        if (own > 0 && want > own) o.d = scale(it.d, want / own);
        var ownL = combat(it.dl), wantL = R.value(eff, dst, DMG_L);
        if (wantL > ownL) {
          if (ownL > 0) o.dl = scale(it.dl, wantL / ownL);
          else if (combat(o.d) > 0) {
            o.dl = scale(o.d, wantL / combat(o.d));
            o.dl.m_chop = it.dl.m_chop || 0;
            o.dl.m_pickaxe = it.dl.m_pickaxe || 0;
          }
        }
      } else if (unmeasured) {
        if ((r = R.ratio(BLOCK, it.src, dst)) > 1) { o.block *= r; o.blockL *= r; }
        if ((r = R.ratio(DEFL, it.src, dst)) > 1) { o.defl *= r; o.deflL *= r; }
      } else {
        o.block = Math.max(o.block, R.value(eff, dst, BLOCK));
        o.blockL = Math.max(o.blockL, R.value(eff, dst, BLOCK_L));
        o.defl = Math.max(o.defl, R.value(eff, dst, DEFL));
        o.deflL = Math.max(o.deflL, R.value(eff, dst, DEFL_L));
      }
    }
    if (it.useDur) {
      o.dur = Math.max(o.dur, R.value(eff, dst, DUR));
      o.durL = Math.max(o.durL, R.value(eff, dst, DUR_L));
    }
    var q = Math.max(0, it.quality - 1); // the item goes back to quality 1 but keeps what it had
    if (q > 0) {
      if (!shield && cls !== "summon") {
        var now = combat(it.d) + combat(it.dl) * q, c = combat(o.d);
        if (c > 0 && now > c) o.d = scale(o.d, now / c);
      }
      if (shield) {
        o.block = Math.max(o.block, it.block + it.blockL * q);
        o.defl = Math.max(o.defl, it.defl + it.deflL * q);
      }
      if (it.useDur) o.dur = Math.max(o.dur, it.dur + it.durL * q);
    }
    return o;
  }

  function num(v) { return String(Math.round(v * 100) / 100); }
  function pair(base, per) { return per ? num(base) + " (+" + num(per) + ")" : num(base); }
  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { if (k === "text") e.textContent = attrs[k]; else e.setAttribute(k, attrs[k]); });
    (kids || []).forEach(function (c) { if (c) e.appendChild(c); });
    return e;
  }
  function select(options, value) {
    var s = el("select", { "class": "pov-calc-input" });
    options.forEach(function (o) { var opt = el("option", { value: o[0], text: o[1] }); s.appendChild(opt); });
    if (value != null) s.value = value;
    return s;
  }
  function field(label, input) { return el("label", { "class": "pov-calc-field" }, [el("span", { text: label }), input]); }
  function numInput(v) { return el("input", { "class": "pov-calc-input", type: "number", step: "any", min: "0", value: v || 0 }); }

  function Calc(root, data) {
    var u = data.ui, self = this;
    this.data = data;
    this.R = new Refs(data);
    this.root = root;
    this.byName = {};
    this.byId = {};
    data.items.forEach(function (i) { self.byName[i.name] = i; self.byId[i.id] = i; });

    this.base = el("input", { "class": "pov-calc-input pov-calc-wide", placeholder: u.custom, autocomplete: "off",
                              role: "combobox", "aria-expanded": "false" });
    this.list = el("ul", { "class": "pov-calc-list", role: "listbox" });
    this.list.hidden = true;
    this.active = -1;
    this.hands = select([["1h", u.h1], ["2h", u.h2], ["bow", u.bow], ["shield", u.shield], ["summon", u.summon]], "1h");
    this.kind = select(data.kinds, data.kinds.length ? data.kinds[0][0] : "");
    this.shieldKind = select([["round", u.round], ["tower", u.tower], ["buckler", u.buckler]], "round");
    this.biome = select(data.stages.map(function (s, i) { return [String(i), s]; }), "0");
    this.quality = numInput(1);
    this.quality.setAttribute("min", "1");
    this.useDur = el("input", { type: "checkbox", checked: "checked" });
    this.dur = numInput(0); this.durL = numInput(0);
    this.block = numInput(0); this.blockL = numInput(0);
    this.defl = numInput(0); this.deflL = numInput(0);
    // One table of stats, at quality 1 and per quality: damage types for weapons, block and parry for shields.
    this.dmg = {};
    function statRow(label, a, b) {
      return el("tr", {}, [el("td", { text: label }), el("td", {}, [a]), el("td", {}, [b])]);
    }
    this.dmgRows = data.damage.map(function (d) {
      self.dmg[d[0]] = [numInput(0), numInput(0)];
      return statRow(d[1], self.dmg[d[0]][0], self.dmg[d[0]][1]);
    });
    this.shieldRows = [statRow(u.block, this.block, this.blockL), statRow(u.parry, this.defl, this.deflL)];
    this.durRow = statRow(u.durability, this.dur, this.durL);
    var rows = this.dmgRows.concat(this.shieldRows, [this.durRow]);
    this.statBox = el("table", { "class": "pov-calc-dmg" }, [
      el("thead", {}, [el("tr", {}, [el("th", { text: "" }), el("th", { text: u.at_q1 }), el("th", { text: u.per_quality })])]),
      el("tbody", {}, rows)]);
    this.kindField = field(u.kind, this.kind);
    this.shieldField = field(u.shield_kind, this.shieldKind);
    this.out = el("div", { "class": "pov-calc-out" });

    root.innerHTML = "";
    root.appendChild(el("div", { "class": "pov-calc" }, [
      el("div", { "class": "pov-calc-row" }, [el("div", { "class": "pov-calc-field pov-calc-combo" },
                                                [el("span", { text: u.base }), this.base, this.list])]),
      el("div", { "class": "pov-calc-row" }, [field(u.hands, this.hands), this.kindField, this.shieldField,
                                             field(u.biome, this.biome), field(u.quality, this.quality)]),
      el("p", { "class": "pov-calc-note", text: u.biome_note }),
      el("div", { "class": "pov-calc-row" }, [el("label", { "class": "pov-calc-field pov-calc-check" },
                                                    [this.useDur, el("span", { text: u.uses_durability })])]),
      this.statBox,
      this.out]));

    this.base.addEventListener("input", function () { self.search(); });
    this.base.addEventListener("focus", function () { self.search(); });
    this.base.addEventListener("blur", function () { setTimeout(function () { self.close(); }, 150); });
    this.base.addEventListener("keydown", function (e) { self.key(e); });
    this.list.addEventListener("mousedown", function (e) {
      var li = e.target.closest("li");
      if (li) { e.preventDefault(); self.pick(self.byId[li.dataset.id]); }
    });
    root.addEventListener("input", function (e) { if (e.target !== self.base) self.update(); });
    root.addEventListener("change", function (e) { if (e.target !== self.base) self.update(); });
    // A base page links here with its item in the address: tools/ascension/#SwordIron.
    var first = this.byId[decodeURIComponent(window.location.hash.slice(1))] || data.items[0];
    if (first) this.pick(first); else this.update();
  }

  // The item search: every base whose name has what is typed, at most 50.
  Calc.prototype.search = function () {
    var q = this.base.value.trim().toLowerCase(), self = this, n = 0;
    this.list.innerHTML = "";
    this.active = -1;
    this.data.items.forEach(function (i) {
      if (n >= 50 || (q && i.name.toLowerCase().indexOf(q) < 0)) return;
      n++;
      self.list.appendChild(el("li", { role: "option", "data-id": i.id, text: i.name }));
    });
    this.list.hidden = n === 0;
    this.base.setAttribute("aria-expanded", String(n > 0));
  };
  Calc.prototype.close = function () { this.list.hidden = true; this.base.setAttribute("aria-expanded", "false"); };
  Calc.prototype.pick = function (i) {
    if (!i) return;
    this.base.value = i.name;
    this.close();
    this.fill(i);
  };
  Calc.prototype.key = function (e) {
    var items = this.list.querySelectorAll("li");
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (this.list.hidden) this.search();
      if (!items.length) return;
      e.preventDefault();
      this.active = (this.active + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
      items.forEach(function (li, n) { li.classList.toggle("pov-calc-active", n === this.active); }, this);
      items[this.active].scrollIntoView({ block: "nearest" });
    } else if (e.key === "Enter") {
      var li = items[this.active >= 0 ? this.active : 0];
      if (li && !this.list.hidden) { e.preventDefault(); this.pick(this.byId[li.dataset.id]); }
    } else if (e.key === "Escape") this.close();
  };

  Calc.prototype.fill = function (i) {
    var parts = i.cls.split("/"), self = this;
    if (i.cls === "summon") this.hands.value = "summon";
    else if (i.cls.indexOf("shield:") === 0) { this.hands.value = "shield"; this.shieldKind.value = i.cls.slice(7); }
    else { this.hands.value = parts[1]; this.kind.value = parts[0]; }
    this.biome.value = String(i.src);
    this.quality.value = 1;
    this.quality.setAttribute("max", String(i.maxQ || 1));
    this.useDur.checked = !!i.useDur;
    Object.keys(this.dmg).forEach(function (k) { self.dmg[k][0].value = i.d[k] || 0; self.dmg[k][1].value = i.dl[k] || 0; });
    ["dur", "durL", "block", "blockL", "defl", "deflL"].forEach(function (k) { self[k].value = i[k] || 0; });
    this.update();
  };

  Calc.prototype.item = function () {
    var h = this.hands.value, self = this, d = {}, dl = {};
    Object.keys(this.dmg).forEach(function (k) {
      var a = parseFloat(self.dmg[k][0].value) || 0, b = parseFloat(self.dmg[k][1].value) || 0;
      if (a) d[k] = a;
      if (b) dl[k] = b;
    });
    var f = function (x) { return parseFloat(x.value) || 0; };
    return { hands: h, cls: h === "summon" ? "summon" : h === "shield" ? "shield:" + this.shieldKind.value : this.kind.value + "/" + h,
             src: parseInt(this.biome.value, 10) || 0, quality: Math.max(1, Math.floor(f(this.quality))), useDur: this.useDur.checked,
             d: d, dl: dl, dur: f(this.dur), durL: f(this.durL), block: f(this.block), blockL: f(this.blockL),
             defl: f(this.defl), deflL: f(this.deflL) };
  };

  Calc.prototype.update = function () {
    var u = this.data.ui, data = this.data, R = this.R, it = this.item(), h = it.hands, out = this.out;
    var weapon = h !== "shield" && h !== "summon";
    this.kindField.style.display = weapon ? "" : "none";
    this.shieldField.style.display = h === "shield" ? "" : "none";
    this.shieldRows.forEach(function (r) { r.style.display = h === "shield" ? "" : "none"; });
    this.dmgRows.forEach(function (r) { r.style.display = weapon ? "" : "none"; });
    this.durRow.style.display = it.useDur ? "" : "none";
    out.innerHTML = "";
    if (weapon && combat(it.d) < 5) { out.appendChild(el("p", { text: u.not_eligible })); return; }
    var rows = data.targets.filter(function (t) { return t.stage > it.src; });
    if (!rows.length) { out.appendChild(el("p", { text: u.none })); return; }
    var head = [u.essence, u.biome_col];
    if (weapon) head.push(u.damage_col);
    if (h === "shield") head.push(u.block, u.parry);
    if (it.useDur) head.push(u.durability);
    var curve = false;
    // Each stat with how much it changed from the row before (the first row: from the item as it is).
    var prev = { dmg: combat(it.d) + combat(it.dl) * (it.quality - 1), block: it.block + it.blockL * (it.quality - 1),
                 defl: it.defl + it.deflL * (it.quality - 1), dur: it.dur + it.durL * (it.quality - 1) };
    function cell(text, now, key) {
      var td = el("td", { text: text }), was = prev[key];
      prev[key] = now;
      if (was > 0 && Math.abs(now / was - 1) >= 0.0005) {
        var p = (now / was - 1) * 100;
        td.appendChild(el("span", { "class": "pov-calc-step" + (p < 0 ? " pov-calc-down" : ""),
                                    text: (p > 0 ? "+" : "") + num(p) + "%" }));
      }
      return td;
    }
    var body = rows.map(function (t) {
      var o = compute(R, it, t.stage);
      var cells = [el("td", { text: t.name }), el("td", { text: data.stages[t.stage] + " (" + t.level + ")" })];
      curve = curve || o.curve;
      if (weapon) cells.push(cell(data.damage.filter(function (d) { return o.d[d[0]] || o.dl[d[0]]; })
        .map(function (d) { return d[1] + " " + pair(o.d[d[0]] || 0, o.dl[d[0]] || 0); }).join(", "), combat(o.d), "dmg"));
      if (h === "shield") cells.push(cell(pair(o.block, o.blockL), o.block, "block"), cell(pair(o.defl, o.deflL), o.defl, "defl"));
      if (it.useDur) cells.push(cell(pair(o.dur, o.durL), o.dur, "dur"));
      return el("tr", {}, cells);
    });
    out.appendChild(el("p", {}, [el("strong", { text: u.result })]));
    out.appendChild(el("p", { "class": "pov-calc-note", text: u.step_note }));
    out.appendChild(el("div", { "class": "md-typeset__scrollwrap" }, [el("div", { "class": "md-typeset__table" }, [
      el("table", {}, [el("thead", {}, [el("tr", {}, head.map(function (c) { return el("th", { text: c }); }))]), el("tbody", {}, body)])])]));
    if (curve) out.appendChild(el("p", { "class": "pov-calc-note", text: u.curve_note }));
  };

  var cache = {};
  function boot() {
    var root = document.getElementById("pov-ascension");
    if (!root) return;
    var src = new URL(root.dataset.src, window.location.href).href;
    (cache[src] || (cache[src] = fetch(src).then(function (r) { return r.json(); })))
      .then(function (data) { if (document.body.contains(root)) new Calc(root, data); });
  }

  // Material/Zensical instant navigation swaps pages without a reload; document$ fires each time.
  if (window.document$) window.document$.subscribe(boot);
  else document.addEventListener("DOMContentLoaded", boot);
})();
