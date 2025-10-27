"use client";

import { CopilotSidebar } from "@copilotkit/react-ui";
import { handleThumbsUp, handleThumbsDown } from "./feedback";

var sidebarInstructions = `
You are a medical assistant called Dr. Indigo. Help the user with their medical questions and ONLY use the tools.
Only respond with the response from the tools, do not provide any additional commentary.`;

export default function Home() {
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
