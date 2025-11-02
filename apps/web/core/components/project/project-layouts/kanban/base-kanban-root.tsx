"use client";
import type { FC } from "react";
import { useCallback, useEffect, useRef } from "react";
import { combine } from "@atlaskit/pragmatic-drag-and-drop/combine";
import { autoScrollForElements } from "@atlaskit/pragmatic-drag-and-drop-auto-scroll/element";
import { observer } from "mobx-react";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useProject } from "@/hooks/store/use-project";
import { useProjectFilter } from "@/hooks/store/use-project-filter";
import { useProjectKanbanView } from "@/hooks/store/use-project-kanban-view";
import { useUserPermissions } from "@/hooks/store/user";
import { useProjectGroupDragNDrop } from "@/hooks/use-project-group-dragndrop";
import { ProjectKanBan } from "./default";
import { ProjectKanBanSwimLanes } from "./swimlanes";

export const BaseProjectKanbanRoot: FC = observer(() => {
  const { getProjectById, getGroupedProjectIds } = useProject();
  const { currentWorkspaceDisplayFilters } = useProjectFilter();
  const { getCanUserDragDrop } = useProjectKanbanView();
  const { allowPermissions } = useUserPermissions();

  const containerRef = useRef<HTMLDivElement | null>(null);

  const groupBy = currentWorkspaceDisplayFilters?.group_by;
  const subGroupBy = currentWorkspaceDisplayFilters?.sub_group_by;
  const orderBy = currentWorkspaceDisplayFilters?.order_by;

  const isDragAllowed = getCanUserDragDrop(groupBy, subGroupBy) && allowPermissions([EUserPermissions.ADMIN, EUserPermissions.MEMBER], EUserPermissionsLevel.WORKSPACE);

  const handleOnDrop = useProjectGroupDragNDrop(orderBy, groupBy, subGroupBy);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    return combine(
      autoScrollForElements({
        element,
      })
    );
  }, []);

  const getGroupedProjects = useCallback(
    (groupByParam: string, subGroupByParam?: string) => {
      return getGroupedProjectIds(groupByParam, subGroupByParam) as any;
    },
    [getGroupedProjectIds]
  );

  if (!groupBy || groupBy === "none") {
    return (
      <div className="flex items-center justify-center h-full text-custom-text-300">
        Please select a grouping option to view projects in kanban layout.
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative h-full w-full overflow-hidden">
      <div className="h-full w-full overflow-x-auto overflow-y-auto p-4">
        {subGroupBy && subGroupBy !== "none" ? (
          <ProjectKanBanSwimLanes
            groupBy={groupBy}
            subGroupBy={subGroupBy}
            getGroupedProjectIds={getGroupedProjects}
            getProjectById={getProjectById}
            isDragAllowed={isDragAllowed}
            handleOnDrop={handleOnDrop}
          />
        ) : (
          <ProjectKanBan
            groupBy={groupBy}
            getGroupedProjectIds={getGroupedProjects}
            getProjectById={getProjectById}
            isDragAllowed={isDragAllowed}
            handleOnDrop={handleOnDrop}
          />
        )}
      </div>
    </div>
  );
});
