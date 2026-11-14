// Shared shell for every page: nav, footer, smooth scroll, reveals, cursor.
import './styles.css';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { SplitText } from 'gsap/SplitText';
import Lenis from 'lenis';

gsap.registerPlugin(ScrollTrigger, SplitText);
export { gsap, ScrollTrigger, SplitText };
export const REDUCE = matchMedia('(prefers-reduced-motion: reduce)').matches;
export const FINE = matchMedia('(hover: hover) and (pointer: fine)').matches;
export const $ = (s, el = document) => el.querySelector(s);
export const $$ = (s, el = document) => [...el.querySelectorAll(s)];
export const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
export const lerp = (a, b, t) => a + (b - a) * t;
export const DPR = Math.min(2, window.devicePixelRatio || 1);
export const EASE = 'expo.out';

const PAGES = [
  ['index.html', 'Home'],
  ['nisar.html', 'NISAR'],
  ['insights.html', 'Insights'],
  ['collaborators.html', 'Collaborators'],
  ['about.html', 'About us'],
];

export const loadStats = () => fetch(import.meta.env.BASE_URL + 'data/stats.json').then((r) => r.json());

/** Size a canvas to its CSS box. Returns true when the size changed. */
export function fit(c) {
  const w = Math.round(c.clientWidth * DPR), h = Math.round(c.clientHeight * DPR);
  if (c.width === w && c.height === h) return false;
  c.width = w; c.height = h;
  return true;
}
/** Run draw() every frame, but only while el is on screen. */
export function whileVisible(el, draw) {
  let on = false, raf = 0;
  const tick = () => { if (!on) return; draw(); raf = requestAnimationFrame(tick); };
  new IntersectionObserver(([e]) => {
    on = e.isIntersecting;
    cancelAnimationFrame(raf);
    if (on) tick();
  }, { rootMargin: '80px' }).observe(el);
}

function shell() {
  const here = location.pathname.split('/').pop() || 'index.html';
  const links = PAGES.map(([h, t]) => `<a href="${h}"${h === here ? ' aria-current="page"' : ''}>${t}</a>`).join('');
  document.body.insertAdjacentHTML('afterbegin', `
    <div class="prog" aria-hidden="true"></div>
    <header class="nav${document.body.dataset.nav === 'dark' ? ' on-dark' : ''}">
      <a class="brand" href="index.html"><i aria-hidden="true"></i>CoastLens</a>
      <nav aria-label="Main">${links}</nav>
      <button class="menu-btn mono" aria-expanded="false">Menu</button>
    </header>
    <div class="cursor" aria-hidden="true"><span></span></div>`);
  document.body.insertAdjacentHTML('beforeend', `
    <footer>
      <p class="big">CoastLens</p>
      <div class="cols">
        <p>An independent student project from FAST-NUCES Karachi for the NASA Space Apps Challenge 2026, &ldquo;Dancing with the SARs&rdquo;. Not affiliated with or endorsed by NASA, ISRO or any organization named on this site.</p>
        <nav aria-label="Footer" class="mono">${links}</nav>
      </div>
    </footer>`);
  const nav = $('.nav'), btn = $('.menu-btn');
  btn.onclick = () => {
    const open = nav.classList.toggle('open');
    btn.setAttribute('aria-expanded', open);
    btn.textContent = open ? 'Close' : 'Menu';
  };
}

function smooth() {
  const nav = $('.nav'), prog = $('.prog');
  let last = 0;
  const onScroll = (y) => {
    const max = document.documentElement.scrollHeight - innerHeight;
    prog.style.transform = `scaleX(${max > 0 ? y / max : 0})`;
    nav.classList.toggle('solid', y > 60);
    if (!nav.classList.contains('open')) nav.classList.toggle('hide', y > last && y > 400);
    last = y;
  };
  if (REDUCE) { addEventListener('scroll', () => onScroll(scrollY), { passive: true }); return; }
  const lenis = new Lenis({ duration: 1.5, easing: (t) => 1 - Math.pow(1 - t, 4), smoothWheel: true });
  lenis.on('scroll', (e) => { ScrollTrigger.update(); onScroll(e.scroll); });
  gsap.ticker.add((t) => lenis.raf(t * 1000));
  gsap.ticker.lagSmoothing(0);
  $$('a[href^="#"]').forEach((a) => a.addEventListener('click', (e) => {
    const t = $(a.getAttribute('href'));
    if (t) { e.preventDefault(); lenis.scrollTo(t, { duration: 2 }); }
  }));
}

function reveals() {
  if (REDUCE) return;
  document.documentElement.classList.add('js-anim');
  // headline lines rise out of a mask
  $$('[data-split]').forEach((el) => {
    SplitText.create(el, {
      type: 'lines', mask: 'lines', linesClass: 'split-line', autoSplit: true,
      onSplit: (s) => gsap.from(s.lines, {
        yPercent: 110, duration: 1.5, ease: EASE, stagger: 0.12,
        scrollTrigger: { trigger: el, start: 'top 86%', once: true },
      }),
    });
  });
  $$('[data-reveal]').forEach((el) => gsap.to(el, {
    opacity: 1, y: 0, duration: 1.4, ease: EASE, delay: +el.dataset.reveal || 0,
    scrollTrigger: { trigger: el, start: 'top 90%', once: true },
  }));
  // depth: elements drift at different speeds
  $$('[data-parallax]').forEach((el) => gsap.fromTo(el, { yPercent: -el.dataset.parallax * 50 }, {
    yPercent: el.dataset.parallax * 50, ease: 'none',
    scrollTrigger: { trigger: el.closest('section') || el, start: 'top bottom', end: 'bottom top', scrub: 0.8 },
  }));
}

function cursor() {
  if (!FINE || REDUCE) return;
  const c = $('.cursor'), label = $('span', c);
  const x = gsap.quickTo(c, 'x', { duration: 0.5, ease: 'power3' }), y = gsap.quickTo(c, 'y', { duration: 0.5, ease: 'power3' });
  addEventListener('pointermove', (e) => { c.classList.add('show'); x(e.clientX); y(e.clientY); });
  document.addEventListener('pointerover', (e) => {
    const big = e.target.closest('[data-cursor]');
    const link = e.target.closest('a, button, select, input, .handle');
    c.classList.toggle('big', !!big && !link);
    c.classList.toggle('link', !!link);
    if (big) label.textContent = big.dataset.cursor;
  });
  document.addEventListener('pointerleave', () => c.classList.remove('show'));
  // magnetic primary buttons
  $$('.btn.solid').forEach((b) => {
    const mx = gsap.quickTo(b, 'x', { duration: 0.8, ease: 'power3' }), my = gsap.quickTo(b, 'y', { duration: 0.8, ease: 'power3' });
    b.addEventListener('pointermove', (e) => {
      const r = b.getBoundingClientRect();
      mx((e.clientX - r.left - r.width / 2) * 0.3); my((e.clientY - r.top - r.height / 2) * 0.3);
    });
    b.addEventListener('pointerleave', () => { mx(0); my(0); });
  });
}

/** Renders the reusable "Finding": measured vs possible explanation vs confidence. */
export function finding({ measured, maybe, confidence, why }) {
  const lvl = { Low: 1, Medium: 2, High: 3 }[confidence] || 0;
  return `<div class="finding">
    <div><span class="tag meas">Measured by satellite</span><p>${measured}</p></div>
    <div><span class="tag maybe">Possible explanation</span><p>${maybe}</p></div>
    <div><span class="tag conf">Confidence</span><p><b>${confidence}.</b> ${why}</p>
      <div class="conf-bar" role="img" aria-label="Confidence ${confidence}">${[1, 2, 3].map((i) => `<i class="${i <= lvl ? 'on' : ''}"></i>`).join('')}</div></div>
  </div>`;
}

export function init() {
  shell();
  smooth();
  // wait for fonts so split lines measure correctly
  (document.fonts?.ready || Promise.resolve()).then(() => { reveals(); ScrollTrigger.refresh(); });
  cursor();
}
