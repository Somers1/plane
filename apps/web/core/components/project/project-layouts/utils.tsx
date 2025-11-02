"use client";
import type { IPragmaticDropPayload, TProject, TProjectGroupByOptions } from "@plane/types";
import { PROJECT_PRIORITIES, PROJECT_STAGES } from "@plane/constants";
import { orderJoinedProjects } from "@plane/utils";

export type ProjectGroupDropLocation = {
  columnId: string;
  groupId: string;
  subGroupId?: string;
  id: string | undefined;
};

export interface IProjectGroupByColumn {
  id: string;
  name: string;
  payload: Record<string, string>;
}

const getStageColumns = (): IProjectGroupByColumn[] => {
  return PROJECT_STAGES.map((stage) => ({
    id: stage.key,
    name: stage.title,
    payload: { stage: stage.key },
  }));
};

const getPriorityColumns = (): IProjectGroupByColumn[] => {
  return PROJECT_PRIORITIES.map((priority) => ({
    id: priority.key,
    name: priority.title,
    payload: { priority: priority.key },
  }));
};

export const getProjectGroupByColumns = (
  groupBy: TProjectGroupByOptions | null | undefined
): IProjectGroupByColumn[] | undefined => {
  if (!groupBy || groupBy === "none") return undefined;
  if (groupBy === "stage") return getStageColumns();
  if (groupBy === "priority") return getPriorityColumns();
  return undefined;
};

export const getSourceFromProjectDropPayload = (payload: IPragmaticDropPayload): ProjectGroupDropLocation | undefined => {
  const { location, source: sourceProject } = payload;
  const sourceProjectData = sourceProject.data;
  let sourceColumnData;
  const sourceDropTargets = location?.initial?.dropTargets ?? [];
  for (const dropTarget of sourceDropTargets) {
    const dropTargetData = dropTarget?.data;
    if (!dropTargetData) continue;
    if (dropTargetData.type === "COLUMN") {
      sourceColumnData = dropTargetData;
    }
  }
  if (sourceProjectData?.id === undefined || !sourceColumnData?.groupId) return;
  return {
    groupId: sourceColumnData.groupId as string,
    subGroupId: sourceColumnData.subGroupId as string,
    columnId: sourceColumnData.columnId as string,
    id: sourceProjectData.id as string,
  };
};

export const getDestinationFromProjectDropPayload = (payload: IPragmaticDropPayload): ProjectGroupDropLocation | undefined => {
  const { location } = payload;
  let destinationProjectData, destinationColumnData;
  const destDropTargets = location?.current?.dropTargets ?? [];
  for (const dropTarget of destDropTargets) {
    const dropTargetData = dropTarget?.data;
    if (!dropTargetData) continue;
    if (dropTargetData.type === "COLUMN" || dropTargetData.type === "DELETE") {
      destinationColumnData = dropTargetData;
    }
    if (dropTargetData.type === "PROJECT") {
      destinationProjectData = dropTargetData;
    }
  }
  if (!destinationColumnData?.groupId) return;
  return {
    groupId: destinationColumnData.groupId as string,
    subGroupId: destinationColumnData.subGroupId as string,
    columnId: destinationColumnData.columnId as string,
    id: (destinationProjectData?.id as string) ?? undefined,
  };
};

export const handleProjectGroupDragDrop = async (
  source: ProjectGroupDropLocation,
  destination: ProjectGroupDropLocation,
  getProjectById: (projectId: string | undefined | null) => TProject | undefined,
  getProjectIdsByGroup: (groupBy: string, groupId: string) => string[],
  updateProjectOnDrop: (workspaceSlug: string, projectId: string, data: Partial<TProject>) => Promise<void>,
  updateProjectView: (workspaceSlug: string, projectId: string, viewProps: any) => Promise<any>,
  workspaceSlug: string,
  groupBy: TProjectGroupByOptions | undefined,
  subGroupBy: TProjectGroupByOptions | undefined,
  shouldResetSortOrder: boolean
) => {
  if (!source.id || !destination.groupId || !groupBy) return;
  const sourceProject = getProjectById(source.id);
  if (!sourceProject) return;
  let updatePayload: Partial<TProject> = {};
  if (groupBy && groupBy !== "none" && source.groupId !== destination.groupId) {
    updatePayload[groupBy as keyof TProject] = destination.groupId === "none" ? null : destination.groupId;
  }
  if (subGroupBy && subGroupBy !== "none" && source.subGroupId && destination.subGroupId && source.subGroupId !== destination.subGroupId) {
    updatePayload[subGroupBy as keyof TProject] = destination.subGroupId === "none" ? null : destination.subGroupId;
  }
  if (Object.keys(updatePayload).length > 0) {
    await updateProjectOnDrop(workspaceSlug, sourceProject.id, updatePayload);
  }
  if (!shouldResetSortOrder) {
    const destinationGroupId = subGroupBy && destination.subGroupId ? destination.subGroupId : destination.groupId;
    const destinationGroupProjects = getProjectIdsByGroup(subGroupBy || groupBy || "stage", destinationGroupId);
    const sourceIndex = destinationGroupProjects.indexOf(source.id);
    const destinationIndex = destination.id ? destinationGroupProjects.indexOf(destination.id) : destinationGroupProjects.length;
    if (sourceIndex === -1) {
      const destinationProjects = destinationGroupProjects.map(id => getProjectById(id)).filter(Boolean) as TProject[];
      const sortOrder = orderJoinedProjects(0, destinationIndex, source.id, destinationProjects);
      if (sortOrder !== undefined) {
        await updateProjectView(workspaceSlug, sourceProject.id, { sort_order: sortOrder });
      }
    } else if (sourceIndex !== destinationIndex) {
      const destinationProjects = destinationGroupProjects.map(id => getProjectById(id)).filter(Boolean) as TProject[];
      const sortOrder = orderJoinedProjects(sourceIndex, destinationIndex, source.id, destinationProjects);
      if (sortOrder !== undefined) {
        await updateProjectView(workspaceSlug, sourceProject.id, { sort_order: sortOrder });
      }
    }
  }
};
