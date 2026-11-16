/* Search: a page whose title is what you typed comes first ("sigil" finds Sigils, "building"
   finds Buildings). The site's search has no stemming and no boost setting, so a list page loses
   to the many items named after it. This wraps the search worker: it keeps the index the page
   sends it, and puts the pages whose title matches the query (singular or plural) at the top of
   the first page of results, removing them from later pages. */
(function () {
  "use strict";
  var Native = window.Worker;
  if (!Native) return;

  var ENDINGS = ["", "s", "es", "ы", "и", "а"]; // plurals, English and Russian

  function norm(s) {
    return String(s || "").replace(/<[^>]*>/g, "").trim().toLowerCase();
  }

  function matches(title, query) {
    if (!query) return false;
    return ENDINGS.some(function (e) {
      return title === query + e || query === title + e;
    });
  }

  function Boosted(url, options) {
    var worker = new Native(url, options);
    if (String(url).indexOf("search") < 0) return worker;
    var docs = [], top = [];

    var post = worker.postMessage.bind(worker);
    worker.postMessage = function (message) {
      if (message && message.type === 0 && message.data && message.data.items) {
        docs = message.data.items;
      } else if (message && message.type === 2 && message.data) {
        var query = norm(message.data.input);
        top = [];
        docs.forEach(function (doc, id) {
          if (doc.level === 1 && matches(norm(doc.title), query)) top.push(id);
        });
        // The plural first: "Bosses" (the list) before "Boss" (the keyword).
        top.sort(function (a, b) { return norm(docs[b].title).length - norm(docs[a].title).length; });
      }
      return post.apply(null, arguments);
    };

    var listeners = [];
    function reorder(event) {
      var m = event.data;
      if (!m || m.type !== 3 || !m.data || !m.data.items || !top.length) return event;
      var first = !m.data.pagination || typeof m.data.pagination.prev === "undefined";
      var rest = m.data.items.filter(function (item) { return top.indexOf(item.id) < 0; });
      var items = first ? top.map(function (id) {
        return m.data.items.find(function (item) { return item.id === id; }) || { id: id, matches: [] };
      }).concat(rest) : rest;
      var data = Object.assign({}, m.data, { items: items });
      return { data: Object.assign({}, m, { data: data }) };
    }

    Object.defineProperty(worker, "onmessage", {
      set: function (fn) {
        if (listeners.length) worker.removeEventListener("message", listeners.pop());
        if (!fn) return;
        var wrapped = function (event) { fn.call(worker, reorder(event)); };
        listeners.push(wrapped);
        worker.addEventListener("message", wrapped);
      },
      get: function () { return null; },
      configurable: true,
    });
    return worker;
  }
  Boosted.prototype = Native.prototype;
  window.Worker = Boosted;
})();
