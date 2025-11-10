"use client";

import { CopilotSidebar } from "@copilotkit/react-ui";
import { handleThumbsUp, handleThumbsDown } from "./feedback";

var sidebarInstructions = `
You are Aubrey, a Novant Health care navigator.
- For every user question, consult the remote "+care-navigator" agent and surface its reply in natural, supportive language.
- Summarize any tool results in complete sentences instead of echoing raw JSON.
- Keep responses concise, empathetic, and easy to follow.`;

export default function Home() {
  const handleThumbsUp = (message) => {
    console.log("Thumbs up:", message);
    // Add your thumbs up feedback logic here
  };

  const handleThumbsDown = (message) => {
    console.log("Thumbs down:", message);
    // Add your thumbs down feedback logic here
  };

  return (
    <CopilotSidebar
      defaultOpen={true}
      instructions={sidebarInstructions}
      labels={{
        title: "Dr. Indigo Assistant",
        initial: "How can I help you today?",
      }}
      onThumbsUp={handleThumbsUp}
      onThumbsDown={handleThumbsDown}
    >
      <div className="min-h-screen flex flex-col items-center justify-center">
        <h1 className="text-6xl font-bold text-gray-800 dark:text-gray-200 mb-4">
          Dr. Indigo
        </h1>
        <div className="text-8xl">
          🩺
        </div>
      </div>
    </CopilotSidebar>
  );
}
