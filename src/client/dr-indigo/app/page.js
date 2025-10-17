import { CopilotSidebar } from "@copilotkit/react-ui";

export default function Home() {
  return (
    <CopilotSidebar
      defaultOpen={true}
      instructions={"You are assisting the user as best as you can. Answer in the best way possible given the data you have."}
      labels={{
        title: "Dr. Indigo Assistant",
        initial: "How can I help you today?",
      }}
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
