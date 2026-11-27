/* WebGL1 background: field shader + CPU particles (port of docs/design/filum-prototype.html).
   No third-party libraries. One requestAnimationFrame loop, paused while the tab is hidden.
   create() returns null when WebGL is unavailable or the shaders fail to compile; the caller
   then hides the canvas and the CSS gradient stays visible. */

export type PulseKind = "tap" | "key" | "ok" | "err" | "ai" | "solved";

export interface FxEngine {
  pulse(x: number, y: number, kind: PulseKind): void;
  energy(amount: number): void;
  destroy(): void;
}

type RGB = [number, number, number];
const BASE: RGB = [0.62, 0.74, 1.0];
const COL: Record<PulseKind, RGB> = {
  ok: [0.23, 0.88, 0.63], err: [1.0, 0.36, 0.48], ai: [0.36, 0.78, 1.0],
  solved: [1.0, 0.70, 0.14], tap: [0.70, 0.82, 1.0], key: [0.75, 0.85, 1.0],
};

const MIN_PARTICLES = 110;
const MAX_PARTICLES = 320;
const MAX_PARTICLES_NARROW = 160;   // screens narrower than 600 css px
const AREA_PER_PARTICLE = 5200;
const REPEL_RADIUS = 150;

export function particleCount(w: number, h: number): number {
  const max = w < 600 ? MAX_PARTICLES_NARROW : MAX_PARTICLES;
  return Math.max(MIN_PARTICLES, Math.min(max, Math.round((w * h) / AREA_PER_PARTICLE)));
}

const BG_VS = "attribute vec2 a;void main(){gl_Position=vec4(a,0.,1.);}";
const BG_FS =
  "precision mediump float;uniform vec2 r;uniform float t;uniform vec2 m;uniform vec3 tint;uniform float k;" +
  "void main(){vec2 uv=gl_FragCoord.xy/r;float asp=r.x/r.y;" +
  "vec3 c=mix(vec3(.040,.070,.190),vec3(.060,.100,.270),uv.y);" +
  "float w=sin(uv.x*3.+t*.10)+sin(uv.y*4.-t*.08)+sin((uv.x+uv.y)*5.+t*.06);" +
  "c+=vec3(.05,.09,.22)*(.5+.5*w/3.)*.7;" +
  "float d=distance(uv*vec2(asp,1.),m*vec2(asp,1.));" +
  "c+=vec3(.20,.42,1.)*exp(-d*3.4)*.11;" +
  "c+=tint*k*exp(-distance(uv*vec2(asp,1.),vec2(.5*asp,.45))*1.6)*.35;" +
  "gl_FragColor=vec4(c,1.);}";
const PT_VS =
  "attribute vec2 p;attribute float s;attribute vec4 c;uniform vec2 r;uniform float dpr;varying vec4 vc;" +
  "void main(){vc=c;gl_Position=vec4(p/r*2.-1.,0.,1.);gl_PointSize=s*dpr;}";
const PT_FS =
  "precision mediump float;varying vec4 vc;" +
  "void main(){float d=length(gl_PointCoord-.5)*2.;float a=1.-smoothstep(.0,1.,d);a*=a;gl_FragColor=vec4(vc.rgb,vc.a*a);}";

interface Pulse { x: number; y: number; t: number; c: RGB; s: number; life: number }

interface GLRes {
  bg: WebGLProgram; pt: WebGLProgram; quad: WebGLBuffer; ptBuf: WebGLBuffer;
  bgA: number; bgR: WebGLUniformLocation | null; bgT: WebGLUniformLocation | null; bgM: WebGLUniformLocation | null;
  bgTint: WebGLUniformLocation | null; bgK: WebGLUniformLocation | null;
  ptP: number; ptS: number; ptC: number; ptR: WebGLUniformLocation | null; ptDpr: WebGLUniformLocation | null;
}

function compile(gl: WebGLRenderingContext, vs: string, fs: string): WebGLProgram | null {
  const prog = gl.createProgram();
  if (!prog) return null;
  for (const [type, src] of [[gl.VERTEX_SHADER, vs], [gl.FRAGMENT_SHADER, fs]] as const) {
    const s = gl.createShader(type);
    if (!s) return null;
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) return null;
    gl.attachShader(prog, s);
  }
  gl.linkProgram(prog);
  return gl.getProgramParameter(prog, gl.LINK_STATUS) ? prog : null;
}

function setup(gl: WebGLRenderingContext): GLRes | null {
  const bg = compile(gl, BG_VS, BG_FS);
  const pt = compile(gl, PT_VS, PT_FS);
  const quad = gl.createBuffer();
  const ptBuf = gl.createBuffer();
  if (!bg || !pt || !quad || !ptBuf) return null;
  gl.bindBuffer(gl.ARRAY_BUFFER, quad);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
  return {
    bg, pt, quad, ptBuf,
    bgA: gl.getAttribLocation(bg, "a"), bgR: gl.getUniformLocation(bg, "r"), bgT: gl.getUniformLocation(bg, "t"),
    bgM: gl.getUniformLocation(bg, "m"), bgTint: gl.getUniformLocation(bg, "tint"), bgK: gl.getUniformLocation(bg, "k"),
    ptP: gl.getAttribLocation(pt, "p"), ptS: gl.getAttribLocation(pt, "s"), ptC: gl.getAttribLocation(pt, "c"),
    ptR: gl.getUniformLocation(pt, "r"), ptDpr: gl.getUniformLocation(pt, "dpr"),
  };
}

export interface EngineOptions {
  reducedMotion: boolean;
  /** injectable for tests */
  raf?: (cb: FrameRequestCallback) => number;
  caf?: (id: number) => void;
}

export function createEngine(canvas: HTMLCanvasElement, opts: EngineOptions): FxEngine | null {
  let gl: WebGLRenderingContext | null = null;
  try {
    gl = canvas.getContext("webgl", { antialias: false, alpha: false }) as WebGLRenderingContext | null;
  } catch {
    gl = null;
  }
  if (!gl) return null;
  let res = setup(gl);
  if (!res) return null;

  const raf = opts.raf ?? window.requestAnimationFrame.bind(window);
  const caf = opts.caf ?? window.cancelAnimationFrame.bind(window);
  const reduce = opts.reducedMotion;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  let W = 1, H = 1, N = 0;
  let px = new Float32Array(0), py = px, vx = px, vy = px, ph = px, sz = px, fl = px, fr = px, fg = px, fb = px, data = px;

  function init() {
    W = Math.max(1, window.innerWidth);
    H = Math.max(1, window.innerHeight);
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    const n = particleCount(W, H);
    if (n !== N) {
      N = n;
      px = new Float32Array(N); py = new Float32Array(N); vx = new Float32Array(N); vy = new Float32Array(N);
      ph = new Float32Array(N); sz = new Float32Array(N); fl = new Float32Array(N);
      fr = new Float32Array(N); fg = new Float32Array(N); fb = new Float32Array(N);
      data = new Float32Array(N * 7);
      for (let i = 0; i < N; i++) {
        px[i] = Math.random() * W; py[i] = Math.random() * H;
        ph[i] = Math.random() * 6.28; sz[i] = 2.6 + Math.random() * 3.6;   // 2.6..6.2 px
      }
    }
  }
  init();

  let mx = W / 2, my = H / 2, sx = mx, sy = my, active = false, en = 0, T = 0;
  let tint: RGB = [0, 0, 0], tintK = 0, jit = 0;
  const att = { x: 0, y: 0, k: 0 };
  const pulses: Pulse[] = [];

  function step(dt: number) {
    T += dt; en *= Math.max(0, 1 - 1.4 * dt); tintK *= Math.max(0, 1 - 1.1 * dt);
    jit *= Math.max(0, 1 - 2.2 * dt); att.k *= Math.max(0, 1 - 2.6 * dt);
    sx += (mx - sx) * Math.min(1, dt * 6); sy += (my - sy) * Math.min(1, dt * 6);
    for (let q = pulses.length - 1; q >= 0; q--) { pulses[q].t += dt; if (pulses[q].t > pulses[q].life) pulses.splice(q, 1); }
    const R = REPEL_RADIUS, damp = Math.max(0, 1 - 1.6 * dt);
    for (let i = 0; i < N; i++) {
      const x = px[i], y = py[i], a = ph[i], amp = 7 + en * 40;
      vx[i] += Math.sin(T * 0.31 + a) * amp * dt;
      vy[i] += (Math.cos(T * 0.27 + a * 1.3) * amp - 1.5) * dt;
      if (jit > 0.02) { vx[i] += (Math.random() - 0.5) * jit * 1400 * dt; vy[i] += (Math.random() - 0.5) * jit * 1400 * dt; }
      if (att.k > 0.03) {
        const ax = att.x - x, ay = att.y - y, ad = Math.sqrt(ax * ax + ay * ay) + 1;
        if (ad < 380) {
          const af = att.k * (1 - ad / 380) * 900;
          vx[i] += (ax / ad) * af * dt; vy[i] += (ay / ad) * af * dt;
          fl[i] = Math.max(fl[i], att.k * 0.25); fr[i] = COL.ok[0]; fg[i] = COL.ok[1]; fb[i] = COL.ok[2];
        }
      }
      if (active) {
        const dx = x - mx, dy = y - my, d2 = dx * dx + dy * dy;
        if (d2 < R * R && d2 > 1) {
          const d = Math.sqrt(d2);
          let f = 1 - d / R; f *= f * 900;
          // repulsion + a small swirl (tangential component)
          vx[i] += ((dx / d) * f + (-dy / d) * f * 0.45) * dt;
          vy[i] += ((dy / d) * f + (dx / d) * f * 0.45) * dt;
          fl[i] = Math.max(fl[i], 0.18 * (1 - d / R)); fr[i] = 0.55; fg[i] = 0.72; fb[i] = 1;
        }
      }
      for (const P of pulses) {
        if (P.t < 0) continue;
        const ddx = x - P.x, ddy = y - P.y, dd = Math.sqrt(ddx * ddx + ddy * ddy) + 0.001;
        const k = 1 - Math.abs(dd - P.t * 560) / 90;
        if (k > 0) {
          const g = k * P.s * (1 - P.t / P.life);
          vx[i] += (ddx / dd) * g * 520 * dt; vy[i] += (ddy / dd) * g * 520 * dt;
          if (g > fl[i]) { fl[i] = Math.min(1, g * 1.3); fr[i] = P.c[0]; fg[i] = P.c[1]; fb[i] = P.c[2]; }
        }
      }
      vx[i] *= damp; vy[i] *= damp; px[i] += vx[i] * dt; py[i] += vy[i] * dt;
      if (px[i] < -10) px[i] = W + 10; else if (px[i] > W + 10) px[i] = -10;
      if (py[i] < -10) py[i] = H + 10; else if (py[i] > H + 10) py[i] = -10;
      fl[i] *= Math.max(0, 1 - 1.5 * dt);
    }
  }

  function draw() {
    if (!gl || !res || gl.isContextLost()) return;
    const r = res;
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.disable(gl.BLEND);
    gl.useProgram(r.bg);
    gl.bindBuffer(gl.ARRAY_BUFFER, r.quad);
    gl.enableVertexAttribArray(r.bgA);
    gl.vertexAttribPointer(r.bgA, 2, gl.FLOAT, false, 0, 0);
    gl.uniform2f(r.bgR, canvas.width, canvas.height);
    gl.uniform1f(r.bgT, T);
    gl.uniform2f(r.bgM, sx / W, 1 - sy / H);
    gl.uniform3f(r.bgTint, tint[0], tint[1], tint[2]);
    gl.uniform1f(r.bgK, tintK);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    gl.disableVertexAttribArray(r.bgA);

    for (let i = 0; i < N; i++) {
      const o = i * 7, f = fl[i], inv = 1 - Math.min(1, f * 1.4);
      data[o] = px[i] * dpr; data[o + 1] = (H - py[i]) * dpr; data[o + 2] = sz[i] * (1 + f * 0.9);
      data[o + 3] = BASE[0] * inv + fr[i] * (1 - inv);
      data[o + 4] = BASE[1] * inv + fg[i] * (1 - inv);
      data[o + 5] = BASE[2] * inv + fb[i] * (1 - inv);
      data[o + 6] = 0.4 + 0.12 * Math.sin(T * 0.8 + ph[i]) + Math.min(0.6, f * 0.8);
    }
    gl.useProgram(r.pt);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE);   // additive
    gl.bindBuffer(gl.ARRAY_BUFFER, r.ptBuf);
    gl.bufferData(gl.ARRAY_BUFFER, data, gl.DYNAMIC_DRAW);
    gl.enableVertexAttribArray(r.ptP); gl.vertexAttribPointer(r.ptP, 2, gl.FLOAT, false, 28, 0);
    gl.enableVertexAttribArray(r.ptS); gl.vertexAttribPointer(r.ptS, 1, gl.FLOAT, false, 28, 8);
    gl.enableVertexAttribArray(r.ptC); gl.vertexAttribPointer(r.ptC, 4, gl.FLOAT, false, 28, 12);
    gl.uniform2f(r.ptR, canvas.width, canvas.height);
    gl.uniform1f(r.ptDpr, dpr);
    gl.drawArrays(gl.POINTS, 0, N);
  }

  // ---- loop: at most one requestAnimationFrame at a time ----
  let rafId = 0, last = 0, running = false, lost = false;
  function frame(now: number) {
    rafId = 0;
    if (!running) return;
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    step(dt);
    draw();
    rafId = raf(frame);
  }
  function start() {
    if (reduce || running || lost || document.hidden) return;
    running = true;
    last = performance.now();
    if (!rafId) rafId = raf(frame);
  }
  function stop() {
    running = false;
    if (rafId) { caf(rafId); rafId = 0; }
  }
  function staticFrame() {
    // reduced motion: settle the particles once, draw one still frame, no loop
    for (let k = 0; k < 20; k++) step(0.05);
    draw();
  }

  // ---- listeners ----
  const onMove = (e: PointerEvent) => { mx = e.clientX; my = e.clientY; active = true; };
  const onLeave = () => { active = false; };
  const onResize = () => { init(); if (reduce) draw(); };
  const onVisibility = () => { if (document.hidden) stop(); else start(); };
  const onLost = (e: Event) => { e.preventDefault(); lost = true; stop(); };
  const onRestored = () => {
    lost = false;
    res = gl ? setup(gl) : null;
    if (!res) return;
    if (reduce) staticFrame(); else start();
  };
  window.addEventListener("pointermove", onMove, { passive: true });
  document.documentElement.addEventListener("pointerleave", onLeave);
  window.addEventListener("resize", onResize);
  document.addEventListener("visibilitychange", onVisibility);
  canvas.addEventListener("webglcontextlost", onLost);
  canvas.addEventListener("webglcontextrestored", onRestored);

  if (reduce) staticFrame(); else start();

  return {
    pulse(x, y, kind) {
      if (reduce) return;
      const c = COL[kind] ?? COL.ok, big = kind === "solved", small = kind === "tap" || kind === "key";
      const s = kind === "err" ? 0.7 : big ? 1.2 : kind === "tap" ? 0.45 : kind === "key" ? 0.25 : 0.9;
      const life = big ? 2.4 : small ? 1.0 : 1.6;
      // ok / solved: particles are pulled to the step for ~0.3 s before the wave starts
      const delay = kind === "ok" || big ? -0.3 : 0;
      pulses.push({ x, y, t: delay, c, s, life });
      if (big) pulses.push({ x, y, t: -0.55, c: COL.ok, s: 0.8, life: 2.4 });
      if (kind === "err") { jit = 1; pulses.push({ x, y, t: 0.12, c, s: 0.45, life: 1.3 }); }
      if (kind === "ok" || big) { att.x = x; att.y = y; att.k = big ? 1.2 : 0.8; }
      if (!small) { tint = c; tintK = big ? 1 : 0.7; }
    },
    energy(a) { if (!reduce) en = Math.min(1.2, en + a); },
    destroy() {
      stop();
      window.removeEventListener("pointermove", onMove);
      document.documentElement.removeEventListener("pointerleave", onLeave);
      window.removeEventListener("resize", onResize);
      document.removeEventListener("visibilitychange", onVisibility);
      canvas.removeEventListener("webglcontextlost", onLost);
      canvas.removeEventListener("webglcontextrestored", onRestored);
      if (gl && res && !gl.isContextLost()) {
        gl.deleteProgram(res.bg); gl.deleteProgram(res.pt);
        gl.deleteBuffer(res.quad); gl.deleteBuffer(res.ptBuf);
      }
      res = null;
      gl = null;
    },
  };
}
