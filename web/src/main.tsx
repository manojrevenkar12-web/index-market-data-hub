import { MotionConfig } from "framer-motion";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { Boundary } from "./shared/ui/Boundary";
import "./theme/base.css";

const root = document.getElementById("root");
if (root)
  createRoot(root).render(
    <StrictMode>
      <MotionConfig reducedMotion="user">
        <Boundary>
          <App />
        </Boundary>
      </MotionConfig>
    </StrictMode>,
  );
