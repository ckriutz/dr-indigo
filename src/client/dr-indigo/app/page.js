"use client";

import { CopilotSidebar } from "@copilotkit/react-ui";
import { useMemo } from "react";

var sidebarInstructions = `
You are a medical assistant called Dr. Indigo. Help the user with their medical questions and ONLY use the tools.
Only respond with the response from the tools, do not provide any additional commentary."`;

// Store trace IDs for messages
const messageTraceMap = new Map();

export default function Home() {
  const handleThumbsUp = async (message) => {
    console.log("Thumbs up clicked:", message);
    
    // Try to get trace ID from the message metadata or our map
    const traceId = messageTraceMap.get(message.id);
    
    try {
      // Send feedback to Langfuse via backend endpoint
      const response = await fetch('/api/feedback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          messageId: message.id,
          rating: 1, // 1 for thumbs up
          message: message.content,
          timestamp: new Date().toISOString(),
          traceId: traceId, // Include trace ID if available
        }),
      });

      if (!response.ok) {
        console.error('Failed to send feedback to Langfuse');
      } else {
        const result = await response.json();
        console.log('Thumbs up feedback sent successfully:', result);
      }
    } catch (error) {
      console.error('Error sending thumbs up feedback:', error);
    }
  };

  const handleThumbsDown = async (message) => {
    console.log("Thumbs down clicked:", message);
    
    // Try to get trace ID from the message metadata or our map
    const traceId = messageTraceMap.get(message.id);
    
    try {
      // Send feedback to Langfuse via backend endpoint
      const response = await fetch('/api/feedback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          messageId: message.id,
          rating: -1, // -1 for thumbs down
          message: message.content,
          timestamp: new Date().toISOString(),
          traceId: traceId, // Include trace ID if available
        }),
      });

      if (!response.ok) {
        console.error('Failed to send feedback to Langfuse');
      } else {
        const result = await response.json();
        console.log('Thumbs down feedback sent successfully:', result);
      }
    } catch (error) {
      console.error('Error sending thumbs down feedback:', error);
    }
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

// Export the map so it can be accessed by CopilotKit actions
export { messageTraceMap };
