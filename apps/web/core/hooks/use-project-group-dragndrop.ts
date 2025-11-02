"use client";
import { useParams } from "next/navigation";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TProject, TProjectGroupByOptions, TProjectOrderByOptions } from "@plane/types";
import type { ProjectGroupDropLocation } from "@/components/project/project-layouts/utils";
import { handleProjectGroupDragDrop } from "@/components/project/project-layouts/utils";
import { useProject } from "./store/use-project";

export const useProjectGroupDragNDrop = (
  orderBy: TProjectOrderByOptions | undefined,
  groupBy: TProjectGroupByOptions | undefined,
  subGroupBy?: TProjectGroupByOptions
) => {
  const { workspaceSlug } = useParams();
  const { getProjectById, getProjectIdsByGroup, updateProject, updateProjectView } = useProject();

  const updateProjectOnDrop = async (
    workspaceSlugParam: string,
    projectId: string,
    data: Partial<TProject>
  ) => {
    const errorToastProps = {
      type: TOAST_TYPE.ERROR,
      title: "Error!",
      message: "Error while updating project",
    };
    if (Object.keys(data).length > 0) {
      await updateProject(workspaceSlugParam, projectId, data).catch(() => setToast(errorToastProps));
    }
  };

  const handleOnDrop = async (source: ProjectGroupDropLocation, destination: ProjectGroupDropLocation) => {
    if (
      source.columnId &&
      destination.columnId &&
      destination.columnId === source.columnId &&
      destination.id === source.id
    )
      return;
    if (!workspaceSlug) return;

    await handleProjectGroupDragDrop(
      source,
      destination,
      getProjectById,
      getProjectIdsByGroup,
      updateProjectOnDrop,
      updateProjectView,
      workspaceSlug.toString(),
      groupBy,
      subGroupBy,
      orderBy !== "sort_order"
    ).catch((err) => {
      setToast({
        title: "Error!",
        type: TOAST_TYPE.ERROR,
        message: err?.detail ?? "Failed to perform this action",
      });
    });
  };

  return handleOnDrop;
};
