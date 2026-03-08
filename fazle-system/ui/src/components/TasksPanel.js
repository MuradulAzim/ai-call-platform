"use client";

import { useState, useEffect } from "react";

export default function TasksPanel() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [newTask, setNewTask] = useState({ title: "", description: "", task_type: "reminder", scheduled_at: "" });

  const fetchTasks = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/fazle/tasks");
      if (res.ok) {
        const data = await res.json();
        setTasks(data.tasks || []);
      }
    } catch {
      console.error("Failed to fetch tasks");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks();
  }, []);

  const createTask = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch("/api/fazle/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newTask),
      });
      if (res.ok) {
        setNewTask({ title: "", description: "", task_type: "reminder", scheduled_at: "" });
        setShowForm(false);
        fetchTasks();
      }
    } catch {
      console.error("Failed to create task");
    }
  };

  const statusColors = {
    pending: "bg-yellow-500/20 text-yellow-300",
    executing: "bg-blue-500/20 text-blue-300",
    completed: "bg-green-500/20 text-green-300",
    failed: "bg-red-500/20 text-red-300",
  };

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-gray-800 p-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-200">Task Manager</h2>
          <p className="text-xs text-gray-500">Schedule tasks and reminders</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-fazle-600 hover:bg-fazle-700 text-white px-4 py-2 rounded-lg text-sm"
        >
          {showForm ? "Cancel" : "+ New Task"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={createTask} className="p-4 border-b border-gray-800 space-y-3">
          <input
            type="text"
            value={newTask.title}
            onChange={(e) => setNewTask({ ...newTask, title: e.target.value })}
            placeholder="Task title"
            className="w-full bg-[#1a1a2e] border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-fazle-500"
            required
          />
          <textarea
            value={newTask.description}
            onChange={(e) => setNewTask({ ...newTask, description: e.target.value })}
            placeholder="Description (optional)"
            rows={2}
            className="w-full bg-[#1a1a2e] border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-fazle-500"
          />
          <div className="flex gap-3">
            <select
              value={newTask.task_type}
              onChange={(e) => setNewTask({ ...newTask, task_type: e.target.value })}
              className="bg-[#1a1a2e] border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-fazle-500"
            >
              <option value="reminder">Reminder</option>
              <option value="call">Call</option>
              <option value="summary">Summary</option>
              <option value="custom">Custom</option>
            </select>
            <input
              type="datetime-local"
              value={newTask.scheduled_at}
              onChange={(e) => setNewTask({ ...newTask, scheduled_at: e.target.value })}
              className="bg-[#1a1a2e] border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-fazle-500"
            />
            <button type="submit" className="bg-fazle-600 hover:bg-fazle-700 text-white px-6 py-2 rounded-lg text-sm font-medium">
              Create
            </button>
          </div>
        </form>
      )}

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {loading ? (
          <p className="text-gray-500 text-sm animate-pulse">Loading tasks...</p>
        ) : tasks.length === 0 ? (
          <p className="text-gray-500 text-sm">No tasks yet. Create one to get started.</p>
        ) : (
          tasks.map((task) => (
            <div key={task.id} className="bg-[#1a1a2e] border border-gray-700/50 rounded-xl p-4 space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-gray-200">{task.title}</h3>
                <span className={`text-xs px-2 py-0.5 rounded-full ${statusColors[task.status] || "bg-gray-700 text-gray-300"}`}>
                  {task.status}
                </span>
              </div>
              {task.description && <p className="text-xs text-gray-400">{task.description}</p>}
              <div className="flex items-center gap-3 text-xs text-gray-500">
                <span>{task.task_type}</span>
                {task.scheduled_at && <span>Scheduled: {new Date(task.scheduled_at).toLocaleString()}</span>}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
