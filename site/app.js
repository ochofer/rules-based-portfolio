// The dashboard's only script. Every figure, label and tooltip arrives formatted from the build; this
// script maps colour roles to the palette and draws each chart with Plotly.
(function () {
  "use strict";
  var DATA = JSON.parse(document.getElementById("dashboard-data").textContent);
  var drawn = {};

  function resolve(value, palette) {
    if (typeof value === "string" && value.charAt(0) === "@") {
      var role = value.slice(1);
      if (!(role in palette)) throw new Error("No colour role " + role);
      return palette[role];
    }
    if (Array.isArray(value)) return value.map(function (v) { return resolve(v, palette); });
    if (value && typeof value === "object") {
      var out = {};
      Object.keys(value).forEach(function (k) { out[k] = resolve(value[k], palette); });
      return out;
    }
    return value;
  }

  function merge(base, extra) {
    var out = JSON.parse(JSON.stringify(base));
    Object.keys(extra || {}).forEach(function (k) {
      var v = extra[k];
      if (v && typeof v === "object" && !Array.isArray(v) && out[k] && typeof out[k] === "object") {
        out[k] = merge(out[k], v);
      } else {
        out[k] = v;
      }
    });
    return out;
  }

  function axis(p) {
    return {
      gridcolor: p.grid, linecolor: p.axis, zerolinecolor: p.axis, zeroline: false, showline: true,
      tickfont: { color: p.muted, size: 11 }, title: { font: { color: p.ink2, size: 12 }, standoff: 8 },
      automargin: true, fixedrange: true
    };
  }

  function baseLayout(p, narrow) {
    return {
      paper_bgcolor: p.surface, plot_bgcolor: p.surface,
      font: { family: 'system-ui, -apple-system, "Segoe UI", sans-serif', color: p.ink2, size: 12 },
      margin: { l: 8, r: 24 - 12 * Number(narrow), t: 8, b: 8 },
      xaxis: axis(p), yaxis: axis(p), showlegend: false,
      legend: { orientation: "h", x: 0, y: 1.02, yanchor: "bottom", font: { color: p.ink2, size: 12 } },
      hoverlabel: { bgcolor: p.surface, bordercolor: p.axis, font: { color: p.ink, size: 12 } },
      hovermode: "closest", dragmode: false, bargap: 0.25
    };
  }

  function draw(chart) {
    var el = document.getElementById(chart.id);
    if (!el || !window.Plotly) return;
    var p = DATA.palette.light;
    var narrow = el.clientWidth < 520;
    var layout = merge(baseLayout(p, narrow), resolve(chart.layout || {}, p));
    if (narrow && chart.layout_narrow) layout = merge(layout, resolve(chart.layout_narrow, p));
    var traces = resolve(chart.traces, p);
    window.Plotly.react(el, traces, layout, { displayModeBar: false, scrollZoom: false, responsive: true, staticPlot: false });
    drawn[chart.id] = true;
  }

  function drawView(view) {
    DATA.charts.forEach(function (c) { if (c.view === view) draw(c); });
  }

  // On a phone the view bar is one row that scrolls sideways. A fade marks each edge with more tabs,
  // and the selected tab is brought into view.
  function barEdges() {
    var bar = document.querySelector(".viewtabs"), wrap = bar && bar.querySelector(".wrap");
    if (!wrap) return;
    bar.classList.toggle("more-r", wrap.scrollWidth - wrap.clientWidth - wrap.scrollLeft > 1);
    bar.classList.toggle("more-l", wrap.scrollLeft > 1);
  }

  function centreTab() {
    var wrap = document.querySelector(".viewtabs .wrap"), sel = wrap && wrap.querySelector('[aria-selected="true"]');
    if (sel && wrap.scrollWidth > wrap.clientWidth) {
      wrap.scrollLeft += sel.getBoundingClientRect().left - wrap.getBoundingClientRect().left - (wrap.clientWidth - sel.offsetWidth) / 2;
    }
    barEdges();
  }

  function show(view, setHash) {
    document.querySelectorAll("section.view").forEach(function (s) {
      s.classList.toggle("active", s.id === "view-" + view);
    });
    document.querySelectorAll(".viewtabs button").forEach(function (b) {
      b.setAttribute("aria-selected", String(b.getAttribute("data-view") === view));
    });
    drawView(view);
    centreTab();
    if (setHash) {
      try { history.replaceState(null, "", "#" + view); } catch (e) { /* the page works without it */ }
    }
  }

  // A link inside a view points at a part of it: show that view, then scroll the part to just below the tabs.
  function viewOf(id) {
    var el = document.getElementById(id);
    if (!el || !el.closest) return null;
    var section = el.closest("section.view");
    if (!section) return null;
    return section.id.replace("view-", "");
  }

  function scrollToPart(id) {
    var el = document.getElementById(id);
    if (!el) return;
    var bar = document.querySelector(".viewtabs");
    var offset = 12;
    if (bar) offset += bar.offsetHeight;
    window.scrollTo(0, Math.max(el.getBoundingClientRect().top + window.pageYOffset - offset, 0));
  }

  function redrawActive() {
    var active = document.querySelector("section.view.active");
    if (active) drawView(active.id.replace("view-", ""));
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".viewtabs button").forEach(function (b) {
      b.addEventListener("click", function () { show(b.getAttribute("data-view"), true); });
    });
    var resizeTimer = null;
    window.addEventListener("resize", function () {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () { redrawActive(); centreTab(); }, 150);
    });
    var tabWrap = document.querySelector(".viewtabs .wrap");
    if (tabWrap) tabWrap.addEventListener("scroll", barEdges, { passive: true });
    var views = DATA.views.map(function (v) { return v.id; });
    function route() {
      var wanted = (location.hash || "").replace("#", "");
      if (views.indexOf(wanted) >= 0) { show(wanted, true); return; }
      var view = viewOf(wanted);
      if (view) { show(view, false); scrollToPart(wanted); return; }
      show(views[0], true);
    }
    document.addEventListener("click", function (event) {
      if (!event.target.closest) return;
      var link = event.target.closest('a[href^="#"]');
      if (!link) return;
      var id = link.getAttribute("href").slice(1);
      var view = viewOf(id);
      if (!view) return;
      event.preventDefault();
      show(view, false);
      scrollToPart(id);
      try { history.replaceState(null, "", "#" + id); } catch (e) { /* the page works without it */ }
    });
    window.addEventListener("hashchange", route);
    route();
    // A page opened at the address of a part: the browser's own jump to it comes after route() and puts the
    // part under the tabs, so the part is scrolled into place again once the page has loaded.
    window.addEventListener("load", function () {
      var id = (location.hash || "").replace("#", "");
      if (views.indexOf(id) < 0 && viewOf(id)) setTimeout(function () { scrollToPart(id); }, 0);
    });
  });

  // A table wider than its column scrolls sideways; a fade at the right edge shows while more of it lies there.
  document.querySelectorAll(".tw").forEach(function (t) {
    function upd() { var s = t.firstElementChild; t.classList.toggle("more", !!s && s.scrollWidth - s.clientWidth - s.scrollLeft > 1); }
    if (!("ResizeObserver" in window)) { t.classList.add("more"); return; }
    t.addEventListener("scroll", upd, true);
    new ResizeObserver(upd).observe(t);
    upd();
  });
})();
