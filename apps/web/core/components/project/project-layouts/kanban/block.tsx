"use client";
import { type FC, useEffect, useRef, useState } from "react";
import { combine } from "@atlaskit/pragmatic-drag-and-drop/combine";
import { draggable, dropTargetForElements } from "@atlaskit/pragmatic-drag-and-drop/element/adapter";
import { observer } from "mobx-react";
import { useParams, useRouter } from "next/navigation";
import { TProject } from "@plane/types";
import { ControlLink } from "@plane/ui";
import { cn } from "@plane/utils";
import { ProjectCard } from "@/components/project/card";
import { useProjectKanbanView } from "@/hooks/store/use-project-kanban-view";

type TProjectKanbanBlockProps = {
  project: TProject;
  isDragAllowed: boolean;
};

export const ProjectKanbanBlock: FC<TProjectKanbanBlockProps> = observer((props) => {
  const { project, isDragAllowed } = props;
  const router = useRouter();
  const { workspaceSlug } = useParams();
  const { setIsDragging } = useProjectKanbanView();
  const [isCurrentBlockDragging, setIsCurrentBlockDragging] = useState(false);
  const [isDraggingOverBlock, setIsDraggingOverBlock] = useState(false);
  const cardRef = useRef<HTMLAnchorElement | null>(null);

  const handleProjectClick = () => {
    router.push(`/${workspaceSlug}/projects/${project.id}/issues`);
  };

  useEffect(() => {
    const element = cardRef.current;
    if (!element) return;
    return combine(
      draggable({
        element,
        dragHandle: element,
        canDrag: () => isDragAllowed,
        getInitialData: () => ({ type: "PROJECT", id: project.id }),
        onDragStart: () => {
          setIsCurrentBlockDragging(true);
          setIsDragging(true);
        },
        onDrop: () => {
          setIsCurrentBlockDragging(false);
          setIsDragging(false);
        },
      }),
      dropTargetForElements({
        element,
        canDrop: ({ source }) => source?.data?.id !== project.id,
        getData: () => ({ id: project.id, type: "PROJECT" }),
        onDragEnter: () => setIsDraggingOverBlock(true),
        onDragLeave: () => setIsDraggingOverBlock(false),
        onDrop: () => setIsDraggingOverBlock(false),
      })
    );
  }, [cardRef?.current, project.id, isDragAllowed, setIsDragging]);

  return (
    <div
      className={cn("group/kanban-block relative mb-3", { "z-[1]": isCurrentBlockDragging })}
      onDragStart={() => {
        if (isDragAllowed) setIsCurrentBlockDragging(true);
      }}
    >
      <ControlLink
        id={`project-${project.id}`}
        href={`/${workspaceSlug}/projects/${project.id}/issues`}
        onClick={handleProjectClick}
        ref={cardRef}
        className={cn("block w-full", {
          "hover:cursor-grab": isDragAllowed,
          "opacity-50": isCurrentBlockDragging,
        })}
      >
        <ProjectCard project={project} disableLink />
      </ControlLink>
    </div>
  );
});
