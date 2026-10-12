(() => {
  "use strict";

  /* ── menú móvil ───────────────────────── */
  const nav = document.querySelector(".nav");
  const menuBtn = nav.querySelector(".menu-btn");
  const setMenu = (open) => {
    nav.dataset.open = String(open);
    menuBtn.setAttribute("aria-expanded", String(open));
    menuBtn.setAttribute("aria-label", open ? "Cerrar menú" : "Abrir menú");
  };
  menuBtn.addEventListener("click", () => setMenu(nav.dataset.open !== "true"));
  nav.querySelectorAll(".nav-links a").forEach((a) => a.addEventListener("click", () => setMenu(false)));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && nav.dataset.open === "true") { setMenu(false); menuBtn.focus(); } });

  /* ── enlace activo en la navegación ───────────────────────── */
  const navMap = new Map([...nav.querySelectorAll(".nav-links a")].map((a) => [a.hash.slice(1), a]));
  const navObserver = new IntersectionObserver((entries) => {
    entries.forEach((en) => {
      if (!en.isIntersecting) return;
      navMap.forEach((a) => a.removeAttribute("aria-current"));
      const link = navMap.get(en.target.id === "aptitudes" ? "experiencia" : en.target.id);
      if (link) link.setAttribute("aria-current", "true");
    });
  }, { rootMargin: "-45% 0px -50% 0px" });
  document.querySelectorAll(".chapter").forEach((s) => navObserver.observe(s));

  /* ── cámara del mundo ───────────────────────── */
  const stage = document.querySelector(".stage");
  const world = document.getElementById("world");
  const svg = world.querySelector("svg");
  const road = svg.getElementById("road-path");
  const traveler = svg.getElementById("traveler");
  const walker = traveler.querySelector(".walker");
  const roadLen = road.getTotalLength();
  const stops = road.dataset.stops.split(",").map(Number);
  const order = ["madrid", "plaza", "campus", "aula", "gante", "correos"];
  const vx = Number(svg.dataset.vx), vy = Number(svg.dataset.vy);
  const VW = svg.viewBox.baseVal.width, VH = svg.viewBox.baseVal.height;

  const chapters = [...document.querySelectorAll(".chapter[data-scene]")];
  const isMobile = () => window.matchMedia("(max-width: 959px)").matches;

  function keyframe(name) {
    const W = stage.clientWidth, H = stage.clientHeight;
    if (name === "overview") {
      const s = Math.min(W / VW, H / VH) * 1.12;
      return { x: (W - VW * s) / 2, y: (H - VH * s) / 2 + H * 0.02, s, t: stops[order.indexOf("aula")] };
    }
    const g = svg.getElementById("scene-" + name);
    const cx = Number(g.dataset.cx) - vx, cy = Number(g.dataset.cy) - vy;
    const s = isMobile()
      ? Math.max(0.3, Math.min(W / 900, H / 600))
      : Math.max(0.42, Math.min(W / 960, H / 760, 1.08));
    const ox = isMobile() ? 0.5 : 0.5, oy = isMobile() ? 0.52 : 0.5;
    return { x: W * ox - cx * s, y: H * oy - cy * s, s, t: stops[order.indexOf(name)] };
  }

  const cam = { x: 0, y: 0, s: 1, t: 0 };
  let lastX = null;
  function render() {
    world.style.transform = `translate3d(${cam.x.toFixed(2)}px, ${cam.y.toFixed(2)}px, 0) scale(${cam.s.toFixed(4)})`;
    const p = road.getPointAtLength(cam.t * roadLen);
    traveler.setAttribute("transform", `translate(${p.x.toFixed(1)} ${p.y.toFixed(1)})`);
    if (lastX !== null && Math.abs(p.x - lastX) > 0.05) {
      walker.setAttribute("transform", p.x < lastX ? "scale(-1 1)" : "");
    }
    lastX = p.x;
  }
  function jumpTo(name) { Object.assign(cam, keyframe(name)); render(); }

  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");

  function initStatic() {
    jumpTo(chapters[0].dataset.scene);
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => { if (en.isIntersecting) jumpTo(en.target.dataset.scene); });
    }, { rootMargin: "-40% 0px -55% 0px" });
    chapters.forEach((c) => io.observe(c));
    window.addEventListener("resize", () => {
      const current = chapters.find((c) => { const r = c.getBoundingClientRect(); return r.top < innerHeight * 0.5 && r.bottom > innerHeight * 0.5; });
      jumpTo((current || chapters[0]).dataset.scene);
    });
  }

  function initScroll() {
    gsap.registerPlugin(ScrollTrigger);
    jumpTo(chapters[0].dataset.scene);
    for (let k = 1; k < chapters.length; k++) {
      const from = chapters[k - 1].dataset.scene, to = chapters[k].dataset.scene;
      gsap.fromTo(cam,
        { x: () => keyframe(from).x, y: () => keyframe(from).y, s: () => keyframe(from).s, t: () => keyframe(from).t },
        {
          x: () => keyframe(to).x, y: () => keyframe(to).y, s: () => keyframe(to).s, t: () => keyframe(to).t,
          ease: "power1.inOut",
          immediateRender: false,
          onUpdate: render,
          scrollTrigger: {
            trigger: chapters[k],
            start: () => (isMobile() ? "top 95%" : "top 85%"),
            end: () => (isMobile() ? "top 55%" : "top 30%"),
            scrub: 0.7,
            invalidateOnRefresh: true,
          },
        });
    }
    ScrollTrigger.addEventListener("refresh", () => {
      const st = ScrollTrigger.getAll();
      if (st.every((t) => t.progress === 0)) jumpTo(chapters[0].dataset.scene);
    });
  }

  if (reduce.matches || typeof gsap === "undefined" || typeof ScrollTrigger === "undefined") initStatic();
  else initScroll();
})();
