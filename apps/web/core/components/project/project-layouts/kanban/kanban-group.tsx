"use client";
import type { FC } from "react";
import { useEffect, useRef, useState } from "react";
import { combine } from "@atlaskit/pragmatic-drag-and-drop/combine";
import { dropTargetForElements } from "@atlaskit/pragmatic-drag-and-drop/element/adapter";
import { autoScrollForElements } from "@atlaskit/pragmatic-drag-and-drop-auto-scroll/element";
import { observer } from "mobx-react";
import { TProject, TProjectGroupByOptions } from "@plane/types";
import { cn } from "@plane/utils";
import { ProjectKanbanBlocksList } from "./blocks-list";
import { getSourceFromProjectDropPayload, getDestinationFromProjectDropPayload, type ProjectGroupDropLocation } from "../utils";

type TProjectKanbanGroupProps = {
  groupId: string;
  subGroupId?: string;
  projectIds: string[];
  getProjectById: (projectId: string) => TProject | undefined;
  isDragAllowed: boolean;
  handleOnDrop: (source: ProjectGroupDropLocation, destination: ProjectGroupDropLocation) => Promise<void>;
  groupBy: TProjectGroupByOptions;
  subGroupBy?: TProjectGroupByOptions;
};

export const ProjectKanbanGroup: FC<TProjectKanbanGroupProps> = observer((props) => {
  const { groupId, subGroupId, projectIds, getProjectById, isDragAllowed, handleOnDrop, groupBy, subGroupBy } = props;
  const columnRef = useRef<HTMLDivElement | null>(null);
  const [isDraggingOverColumn, setIsDraggingOverColumn] = useState(false);

  const columnId = subGroupBy ? `${subGroupId}_${groupId}` : groupId;

  useEffect(() => {
    const element = columnRef.current;
    if (!element || !isDragAllowed) return;
    return combine(
      dropTargetForElements({
        element,
        canDrop: ({ source }) => source?.data?.type === "PROJECT",
        getData: () => ({
          type: "COLUMN",
          groupId,
          subGroupId,
          columnId,
        }),
        onDragEnter: () => setIsDraggingOverColumn(true),
        onDragLeave: () => setIsDraggingOverColumn(false),
        onDrop: (payload) => {
          setIsDraggingOverColumn(false);
          const source = getSourceFromProjectDropPayload(payload);
          const destination = getDestinationFromProjectDropPayload(payload);
          if (!source || !destination) return;
          handleOnDrop(source, destination);
        },
      }),
      autoScrollForElements({
        element,
      })
    );
  }, [groupId, subGroupId, columnId, isDragAllowed, handleOnDrop]);

  return (
    <div
      ref={columnRef}
      className={cn("relative h-full transition-all min-h-[120px] flex flex-col", {
        "bg-custom-background-80 rounded": isDraggingOverColumn,
      })}
    >
      <div className="flex-1 overflow-y-auto vertical-scrollbar scrollbar-md py-2">
        <ProjectKanbanBlocksList
          projectIds={projectIds}
          getProjectById={getProjectById}
          isDragAllowed={isDragAllowed}
        />
      </div>
    </div>
  );
});
