"use client";
import type { FC } from "react";
import { observer } from "mobx-react";
import { TProject, TProjectGroupByOptions } from "@plane/types";
import { PROJECT_PRIORITIES, PROJECT_STAGES } from "@plane/constants";
import { useProjectKanbanView } from "@/hooks/store/use-project-kanban-view";
import { ProjectKanbanGroup } from "./kanban-group";
import { ProjectStageHeader } from "./headers/stage";
import { ProjectPriorityHeader } from "./headers/priority";
import { getProjectGroupByColumns, type ProjectGroupDropLocation } from "../utils";

type TProjectKanBanProps = {
  groupBy: TProjectGroupByOptions;
  getGroupedProjectIds: (groupBy: string) => Record<string, string[]>;
  getProjectById: (projectId: string) => TProject | undefined;
  isDragAllowed: boolean;
  handleOnDrop: (source: ProjectGroupDropLocation, destination: ProjectGroupDropLocation) => Promise<void>;
};

export const ProjectKanBan: FC<TProjectKanBanProps> = observer((props) => {
  const { groupBy, getGroupedProjectIds, getProjectById, isDragAllowed, handleOnDrop } = props;
  const { kanBanToggle, handleKanBanToggle } = useProjectKanbanView();

  const columns = getProjectGroupByColumns(groupBy);
  if (!columns) return null;

  const groupedProjectIds = getGroupedProjectIds(groupBy);

  const renderHeader = (groupId: string, title: string, count: number) => {
    const isCollapsed = kanBanToggle.groupByHeaderMinMax.includes(groupId);
    const toggleCollapse = () => handleKanBanToggle("groupByHeaderMinMax", groupId);

    if (groupBy === "stage") {
      const stage = PROJECT_STAGES.find(s => s.key === groupId);
      return (
        <ProjectStageHeader
          stage={stage?.key as any}
          title={title}
          count={count}
          isCollapsed={isCollapsed}
          toggleCollapse={toggleCollapse}
        />
      );
    }

    if (groupBy === "priority") {
      const priority = PROJECT_PRIORITIES.find(p => p.key === groupId);
      return (
        <ProjectPriorityHeader
          priority={priority?.key as any}
          title={title}
          count={count}
          isCollapsed={isCollapsed}
          toggleCollapse={toggleCollapse}
        />
      );
    }

    return null;
  };

  return (
    <div className="horizontal-scrollbar scrollbar-lg grid auto-cols-[minmax(300px,1fr)] grid-flow-col gap-3 overflow-x-auto">
      {columns.map((column) => {
        const projectIds = groupedProjectIds[column.id] || [];
        const isCollapsed = kanBanToggle.groupByHeaderMinMax.includes(column.id);

        return (
          <div key={column.id} className="flex flex-col gap-2">
            {renderHeader(column.id, column.name, projectIds.length)}
            {!isCollapsed && (
              <ProjectKanbanGroup
                groupId={column.id}
                projectIds={projectIds}
                getProjectById={getProjectById}
                isDragAllowed={isDragAllowed}
                handleOnDrop={handleOnDrop}
                groupBy={groupBy}
              />
            )}
          </div>
        );
      })}
    </div>
  );
});
