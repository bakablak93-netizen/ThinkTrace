/** Minimal WebGL1 stand-in for jsdom: every method is a no-op that "succeeds". */
export function fakeGl(): WebGLRenderingContext {
  const values: Record<string, unknown> = {
    getShaderParameter: true, getProgramParameter: true, isContextLost: false,
    getAttribLocation: 0,
  };
  return new Proxy({}, {
    get(_t, prop: string) {
      if (prop in values) return () => values[prop];
      if (/^[A-Z_0-9]+$/.test(prop)) return 1;   // GL constants
      if (prop.startsWith("create") || prop === "getUniformLocation") return () => ({});
      return () => undefined;
    },
  }) as WebGLRenderingContext;
}
