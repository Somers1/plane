"use client";
import type { FC } from "react";
import { observer } from "mobx-react";
import { PriorityIcon } from "@plane/propel/icons";
import { TProjectPriorities } from "@plane/constants";
import { ProjectHeaderGroupByCard } from "./group-by-card";

type TProjectPriorityHeaderProps = {
  priority: TProjectPriorities;
  title: string;
  count: number;
  isCollapsed: boolean;
  toggleCollapse: () => void;
};

export const ProjectPriorityHeader: FC<TProjectPriorityHeaderProps> = observer((props) => {
  const { priority, title, count, isCollapsed, toggleCollapse } = props;

  return (
    <ProjectHeaderGroupByCard
      icon={<PriorityIcon priority={priority} className="size-4" />}
      title={title}
      count={count}
      issuePayload={{ priority }}
      isCollapsed={isCollapsed}
      toggleCollapse={toggleCollapse}
    />
  );
});
