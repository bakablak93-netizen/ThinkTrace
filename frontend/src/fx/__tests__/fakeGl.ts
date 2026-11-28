/** Minimal WebGL1 stand-in for jsdom: every method is a no-op that "succeeds".
 *  `onPoints` receives every particle buffer the engine uploads (x, y, size, rgba per point). */
export function fakeGl(onPoints?: (data: Float32Array) => void): WebGLRenderingContext {
  const values: Record<string, unknown> = {
    getShaderParameter: true, getProgramParameter: true, isContextLost: false,
    getAttribLocation: 0,
  };
  return new Proxy({}, {
    get(_t, prop: string) {
      if (prop in values) return () => values[prop];
      if (prop === "bufferData") return (_target: number, data: unknown) => {
        if (onPoints && data instanceof Float32Array && data.length > 8) onPoints(data.slice());
      };
      if (/^[A-Z_0-9]+$/.test(prop)) return 1;   // GL constants
      if (prop.startsWith("create") || prop === "getUniformLocation") return () => ({});
      return () => undefined;
    },
  }) as WebGLRenderingContext;
}
