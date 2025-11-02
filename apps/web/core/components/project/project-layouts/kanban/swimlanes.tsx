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

type TProjectKanBanSwimLanesProps = {
  groupBy: TProjectGroupByOptions;
  subGroupBy: TProjectGroupByOptions;
  getGroupedProjectIds: (groupBy: string, subGroupBy?: string) => Record<string, Record<string, string[]>>;
  getProjectById: (projectId: string) => TProject | undefined;
  isDragAllowed: boolean;
  handleOnDrop: (source: ProjectGroupDropLocation, destination: ProjectGroupDropLocation) => Promise<void>;
};

export const ProjectKanBanSwimLanes: FC<TProjectKanBanSwimLanesProps> = observer((props) => {
  const { groupBy, subGroupBy, getGroupedProjectIds, getProjectById, isDragAllowed, handleOnDrop } = props;
  const { kanBanToggle, handleKanBanToggle } = useProjectKanbanView();

  const groupColumns = getProjectGroupByColumns(groupBy);
  const subGroupColumns = getProjectGroupByColumns(subGroupBy);

  if (!groupColumns || !subGroupColumns) return null;

  const groupedProjectIds = getGroupedProjectIds(groupBy, subGroupBy);

  const renderSubGroupHeader = (subGroupId: string, title: string, count: number) => {
    const isCollapsed = kanBanToggle.subgroupByProjectsVisibility.includes(subGroupId);
    const toggleCollapse = () => handleKanBanToggle("subgroupByProjectsVisibility", subGroupId);

    if (subGroupBy === "stage") {
      const stage = PROJECT_STAGES.find(s => s.key === subGroupId);
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

    if (subGroupBy === "priority") {
      const priority = PROJECT_PRIORITIES.find(p => p.key === subGroupId);
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
    <div className="flex flex-col gap-4">
      {subGroupColumns.map((subGroupColumn) => {
        const subGroupProjects = groupedProjectIds[subGroupColumn.id] || {};
        const totalCount = Object.values(subGroupProjects).reduce((acc, ids) => acc + ids.length, 0);
        const isSubGroupCollapsed = kanBanToggle.subgroupByProjectsVisibility.includes(subGroupColumn.id);

        return (
          <div key={subGroupColumn.id} className="flex flex-col gap-2">
            {renderSubGroupHeader(subGroupColumn.id, subGroupColumn.name, totalCount)}
            {!isSubGroupCollapsed && (
              <div className="horizontal-scrollbar scrollbar-lg grid auto-cols-[minmax(300px,1fr)] grid-flow-col gap-3 overflow-x-auto">
                {groupColumns.map((groupColumn) => {
                  const projectIds = subGroupProjects[groupColumn.id] || [];
                  return (
                    <div key={groupColumn.id} className="flex flex-col gap-2">
                      <div className="text-xs font-medium text-custom-text-300 px-1">{groupColumn.name}</div>
                      <ProjectKanbanGroup
                        groupId={groupColumn.id}
                        subGroupId={subGroupColumn.id}
                        projectIds={projectIds}
                        getProjectById={getProjectById}
                        isDragAllowed={isDragAllowed}
                        handleOnDrop={handleOnDrop}
                        groupBy={groupBy}
                        subGroupBy={subGroupBy}
                      />
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
});
