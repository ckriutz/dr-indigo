"use client";

import { CopilotChat } from "@copilotkit/react-ui";
import { handleThumbsUp, handleThumbsDown } from "./feedback";

var chatInstructions = `
You are a medical assistant called Dr. Indigo. Help the user with their medical questions and ONLY use the tools.
Only respond with the response from the tools, do not provide any additional commentary.`;

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
    <div className="flex h-screen">
      {/* Left Sidebar */}
      <aside className="w-64 border-r border-[var(--border-primary)] flex flex-col">
        <div className="p-4">
          <h2 className="text-xl font-bold text-[var(--text-primary)]">Dr. Indigo</h2>
          <div className="text-4xl mt-2">🩺</div>
        </div>
        
        {/* Sidebar content - currently empty, ready for tabs */}
        <nav className="flex-1 p-4">
          {/* Future: Add navigation tabs here */}
        </nav>
      </aside>

      {/* Main Content Area - Chat */}
      <main className="flex-1 flex flex-col">
        <CopilotChat
          instructions={chatInstructions}
          labels={{
            title: "Dr. Indigo Assistant",
            initial: "How can I help you today?",
          }}
          onThumbsUp={handleThumbsUp}
          onThumbsDown={handleThumbsDown}
          className="h-full"
        />
      </main>
    </div>
  );
}
