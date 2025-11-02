import { useContext } from "react";
import type { IProjectKanbanViewStore } from "@/store/project/project-kanban-view.store";
import { StoreContext } from "@/lib/store-context";

export const useProjectKanbanView = (): IProjectKanbanViewStore => {
  const context = useContext(StoreContext);
  if (context === undefined) throw new Error("useProjectKanbanView must be used within StoreProvider");
  return context.projectRoot.projectKanbanView;
};
