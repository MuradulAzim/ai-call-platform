"use client";

import { useState } from "react";
import Sidebar from "../components/Sidebar";
import ChatPanel from "../components/ChatPanel";
import MemoryPanel from "../components/MemoryPanel";
import TasksPanel from "../components/TasksPanel";
import KnowledgePanel from "../components/KnowledgePanel";

export default function Home() {
  const [activeTab, setActiveTab] = useState("chat");

  const panels = {
    chat: <ChatPanel />,
    memory: <MemoryPanel />,
    tasks: <TasksPanel />,
    knowledge: <KnowledgePanel />,
  };

  return (
    <div className="flex h-screen">
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />
      <main className="flex-1 overflow-hidden">{panels[activeTab]}</main>
    </div>
  );
}
