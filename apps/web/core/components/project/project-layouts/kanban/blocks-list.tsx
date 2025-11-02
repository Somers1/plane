"use client";
import type { FC } from "react";
import { observer } from "mobx-react";
import { TProject } from "@plane/types";
import { ProjectKanbanBlock } from "./block";

type TProjectKanbanBlocksListProps = {
  projectIds: string[];
  getProjectById: (projectId: string) => TProject | undefined;
  isDragAllowed: boolean;
};

export const ProjectKanbanBlocksList: FC<TProjectKanbanBlocksListProps> = observer((props) => {
  const { projectIds, getProjectById, isDragAllowed } = props;

  return (
    <div className="flex flex-col gap-3">
      {projectIds.map((projectId) => {
        const project = getProjectById(projectId);
        if (!project) return null;
        return <ProjectKanbanBlock key={project.id} project={project} isDragAllowed={isDragAllowed} />;
      })}
    </div>
  );
});
