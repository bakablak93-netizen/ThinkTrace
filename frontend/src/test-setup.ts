// vitest runs without globals, so @testing-library cannot register its automatic cleanup:
// unmount everything rendered by a test before the next one starts.
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => cleanup());
